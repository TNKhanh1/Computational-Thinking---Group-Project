# M5_01 — Stage 1 Plan: Pure Layer-1 `cross_week_adapter.py` (`P13`) & `controller.py` Core Upgrades
**Trạng thái Stage 1:** `[x] DONE`  
**Nhánh Git:** `v1.0-alpha/m5-cross-week-adaptation-and-repair`  
**Điều kiện tiên quyết:** Đã đọc [`M5_00_Master_Index.md`](./M5_00_Master_Index.md)  
**Phạm vi File của Stage 1 (DUY NHẤT 2 FILE):**
1. **CREATE:** `smartschedule/core/cross_week_adapter.py`
2. **MODIFY:** `smartschedule/core/controller.py`

---

## 1. RÀNG BUỘC KIẾN TRÚC BẮT BUỘC (`INV-1`..`INV-5`) CHO STAGE 1

1. **Độ tinh khiết Layer 1 (`smartschedule/core/cross_week_adapter.py`):**
   - Trong `M7` Wave 2B, bài test AST `test_system_architecture.py` sẽ quét toàn bộ `smartschedule/core/*.py`.
   - Vì vậy `cross_week_adapter.py` **CHỈ ĐƯỢC IMPORT**:
     - Python stdlib: `from __future__ import annotations`, `from datetime import datetime`, `import math`, `import re`, `from typing import Any, Dict, List, Optional, Sequence, Tuple`
     - Nội bộ Layer 1:
       - `from smartschedule.core.config import ALPHA_HEAVY_DEFAULT, ALPHA_LIGHT_DEFAULT`
       - `from smartschedule.core.estimate_buffer import multiplier_for_load`
       - `from smartschedule.core.models import CIRCADIAN_PROFILE_DEFAULTS, CircadianEnergyProfile, CommitmentsProfile, FixedEvent, Task`
       - `from smartschedule.core.utils import MINUTES_PER_SLOT, SLOTS_PER_WEEK, day_time_to_slot, parse_time_to_slot_offset, round_up_to_15`
   - **CẤM TUYỆT ĐỐI** import `smartschedule.api`, `smartschedule.nlp`, `smartschedule.core.storage`, `smartschedule.core.solvers`, `fastapi`, `spacy`, `transformers`, `docling`, `google`.
2. **Không chạm vào `models.py` hoặc `solvers/*`:** Tất cả trường cần thiết (`Task.alpha_light`, `Task.alpha_heavy`, `Task.buffer_mode`, `Task.buffer_multiplier`, `Task.preferred_window`, `Task.work_rhythm`, `Task.min_chunk_min`, `Task.max_chunk_min`, `Task.is_splittable`, `CircadianEnergyProfile.hourly_levels`, `CommitmentsProfile.fixed_events`) **đã có sẵn 100% trong `models.py`**.
3. **Bảo toàn bộ nhớ `INV-5` (`< 350 KB` sau 50 vòng giải):** Không dùng biến cache toàn cục lưu trữ danh sách log hoặc đối tượng `Task`/`ScheduleOutput` ở cấp module.

---

## 2. ĐẶC TẢ CHI TIẾT FILE 1: `smartschedule/core/cross_week_adapter.py`

### 2.1. Hằng số chuẩn hóa ở đầu module
```python
LAMBDA_CATEGORY_EWMA: float = 0.30
KAPPA_EMPIRICAL_BAYES: float = 3.0
RATIO_CLIP_MIN: float = 0.50
RATIO_CLIP_MAX: float = 2.50
ALPHA_SAFE_MIN: float = 1.00
ALPHA_SAFE_MAX: float = 1.60  # Hard ceiling below >=1.70 Over-Buffering Cliff (Pattern P1 / P13)

EFF_RATIO_CLIP_MIN: float = 0.60
EFF_RATIO_CLIP_MAX: float = 1.25
CHRONOTYPE_SHIFT_MARGIN: float = 0.22
CHRONOTYPE_MIN_WINDOW_SAMPLES: int = 2
STATED_ADHERENCE_MAX_FOR_SHIFT: float = 0.75

FATIGUE_PACING_THRESHOLD: float = 0.65
LONG_BLOCK_MIN_THRESHOLD: int = 60
LONG_BLOCK_OVERRUN_RATE_THRESHOLD: float = 0.50
PACED_MIN_CHUNK_MIN: int = 45
PACED_MAX_CHUNK_MIN: int = 75

CHRONIC_DISRUPTION_MIN_COUNT: int = 2
ADVISORY_BUFFER_MAX_RHO: float = 0.90

VALID_WINDOWS: Tuple[str, str, str] = ("MORNING", "AFTERNOON", "EVENING")
```

### 2.2. Chuẩn hóa Log Đầu Vào Kép (`normalize_execution_logs` — Giải quyết `Audit M-5`)
Hàm `adapt_preferences_for_next_week(...)` phải nhận mượt **cả 2 nguồn dữ liệu**:
- **Nguồn A (`InSilicoStudentSimulator` của `M7`):** Mỗi phần tử trong `timeline_logs` có dạng:
  ```python
  {
      "task_id": "T1", "block_id": "B1", "category": "CODING", "cognitive_load": 3,
      "day": "Monday", "window": "MORNING", "start_hour": 8.0,
      "estimated_duration_min": 60, "planned_duration_min": 75, "actual_duration_min": 90,
      "adhered": True, "overrun_min": 15, "fatigue_after": 0.72,
      "disruption_slot_window": "Thursday 19:30-21:00",  # hoặc None
  }
  ```
- **Nguồn B (Người dùng thật từ SQLite `completion_logs` + `workspace_state`):** Mỗi phần tử chỉ có:
  ```python
  {
      "id": 12, "task_id": "T1", "category": "PROJECT",
      "estimated_duration_min": 60, "actual_duration_min": 90,
      "completed_at": "2026-11-25T20:15:00+07:00",
      # Có thể thiếu: window, adhered, cognitive_load, fatigue_after, disruption_slot_window
  }
  ```
- **Quy tắc chuẩn hóa từng dòng log (`_normalize_single_log_entry`):**
  1. **Sắp xếp thời gian tăng dần (cũ $\to$ mới):** Nếu danh sách đến từ `list_completion_logs()` (vốn `ORDER BY id DESC` — mới nhất đứng đầu!), kiểm tra nếu phần tử đầu có `id` lớn hơn phần tử cuối (và các phần tử đều có `id` giảm dần) thì đảo ngược lại (`reversed`) để tính EWMA đúng thứ tự thời gian quá khứ $\to$ hiện tại!
  2. **`category`:** `str(entry.get("category") or "OTHER").strip().upper() or "OTHER"`.
  3. **`estimated_duration_min` ($d_{\text{est}}$) & `actual_duration_min` ($d_{\text{act}}$):** Chỉ tính vào thống kê thời lượng khi `est > 0` và `act > 0` (lưu ý: nếu một ca bị bỏ lỡ hoàn toàn `adhered == False` và `actual_duration_min == 0` hoặc `None`, chỉ tính ca đó vào mẫu số của `AdherenceRate(window)` chứ **không** chia $0 / d_{\text{est}}$ vào EWMA thời lượng!).
  4. **`window` (`MORNING` | `AFTERNOON` | `EVENING` | `NIGHT`):**
     - Nếu `entry.get("window")` hợp lệ $\to$ dùng luôn.
     - Nếu có `start_hour` hoặc `start_time` (`"HH:MM"`) $\to$ suy ra giờ $h \in [0, 23]$: `6 <= h < 12 -> "MORNING"`, `12 <= h < 18 -> "AFTERNOON"`, `18 <= h < 24 -> "EVENING"`, ngược lại `"NIGHT"`.
     - Nếu chỉ có `completed_at` dạng ISO-8601 (`"2026-11-25T20:15:00..."`) $\to$ parse `datetime.fromisoformat(...)` (chuyển về UTC+7 nếu là UTC `"Z"` hoặc `+00:00` bằng `astimezone(timezone(timedelta(hours=7)))`) và lấy `dt.hour` để suy ra `window`!
  5. **`adhered` (`bool`):** Nếu `"adhered"` có trong `entry` $\to$ `bool(entry["adhered"])`; nếu không có (bản ghi từ `completion_logs` tức là người dùng đã bấm hoàn thành!) $\to$ mặc định `True`.

---

### 2.3. Ba Nhánh Thuật Toán Cốt Lõi Trong `adapt_preferences_for_next_week(...)`

#### Chữ ký hàm chính (Khớp 100% với `M5_Le_Tien_Binh.md` & `README_agents.md §2.5`):
```python
def adapt_preferences_for_next_week(
    profile: CommitmentsProfile,
    next_tasks: Sequence[Task],
    timeline_logs: Sequence[Dict[str, Any]],
    kappa: float = KAPPA_EMPIRICAL_BAYES,
    lambda_ewma: float = LAMBDA_CATEGORY_EWMA,
) -> Dict[str, Any]:
```

#### Nhánh 1 — Hệ Số Đệm Co Rút Thực Nghiệm Bayes–EWMA Theo Từng Nhóm Môn (`Shrinkage Category Fallacy Buffers`, Giải quyết `Audit M-2` & Chống Nhân Đôi Buffer)
1. Gom các bản ghi có thực thi (`est > 0`, `act > 0`, và `adhered` không phải `False` rỗng) theo `category` $c$.
2. Với từng bản ghi thứ $k = 1 \dots n_c$ của nhóm $c$:
   - Kẹp tỷ số: $r_k = \min(\text{RATIO\_CLIP\_MAX}, \max(\text{RATIO\_CLIP\_MIN}, d_{\text{act}, k} / d_{\text{est}, k})) \in [0.50, 2.50]$.
   - **Khởi tạo không chệch (`Fix M-2` — Chống Co Rút Kép):**
     - Tại $k = 1$: $\text{EWMA}_c = r_1$
     - Tại $k \ge 2$: $\text{EWMA}_c = \lambda \cdot r_k + (1.0 - \lambda) \cdot \text{EWMA}_c$ (với $\lambda = 0.30$).
3. Với mỗi nhóm môn $c$ xuất hiện trong `timeline_logs` **HOẶC** trong `next_tasks`:
   - Đặt tiên nghiệm theo mức tải nhận thức: $\alpha_0(\text{light}) = 1.20$ (`ALPHA_LIGHT_DEFAULT`), $\alpha_0(\text{heavy}) = 1.35$ (`ALPHA_HEAVY_DEFAULT`).
   - Nếu $n_c == 0$:
     $$\hat{\alpha}_{c,\text{light}} = \alpha_0(\text{light}) = 1.20, \qquad \hat{\alpha}_{c,\text{heavy}} = \alpha_0(\text{heavy}) = 1.35$$
   - Nếu $n_c \ge 1$ (cũng tách riêng mẫu nhẹ `load < 3` và mẫu nặng `load >= 3` nếu nhóm $c$ có mẫu nặng riêng; hoặc dùng $\text{EWMA}_{c,\text{light}}$ / $\text{EWMA}_{c,\text{heavy}}$ fallback về $\text{EWMA}_c$ chung của môn $c$ để khi môn `CODING` mới có 2 mẫu vẫn học mượt cho cả bài nhẹ lẫn bài nặng, đồng thời bài `load >= 3` co rút về tiên nghiệm `1.35` và bài `load < 3` co rút về `1.20`!):
     - Cụ thể, để vừa chính xác theo cả `(category, load>=3)` vừa không bị chia nhỏ mẫu quá mỏng:
       - Tính `ewma_cat_all` ($n_c$ mẫu của cả `category` $c$).
       - Nếu các bản ghi có trường `cognitive_load`: tính thêm `ewma_cat_heavy` ($n_{c,H}$ mẫu có `load >= 3`) và `ewma_cat_light` ($n_{c,L}$ mẫu có `load < 3`).
       - Với mức nhẹ ($\ell \in \{1, 2\}$): nếu $n_{c,L} \ge 1$ dùng $(n_{c,L}, \text{ewma\_cat\_light})$, ngược lại dùng $(n_c, \text{ewma\_cat\_all})$ co rút về $\alpha_0(\text{light}) = 1.20$ (nhưng nếu suy từ mẫu nặng sang nhẹ thì trừ nhẹ độ chênh tiên nghiệm `0.15` trước khi kẹp, hoặc đơn giản dùng trực tiếp `ewma_cat_all` co rút về `1.20` và `1.35` sao cho luôn thỏa $\hat{\alpha}_{c,\text{heavy}} \ge \hat{\alpha}_{c,\text{light}}$!):
         $$\hat{\alpha}_{c,\text{light}} = \text{clip}\!\left(\frac{n_{\text{eff},L}}{n_{\text{eff},L} + \kappa}\text{EWMA}_{\text{eff},L} + \frac{\kappa}{n_{\text{eff},L} + \kappa} \cdot 1.20,\; 1.00,\; 1.60\right)$$
         $$\hat{\alpha}_{c,\text{heavy}} = \text{clip}\!\left(\max\!\left(\hat{\alpha}_{c,\text{light}},\; \frac{n_{\text{eff},H}}{n_{\text{eff},H} + \kappa}\text{EWMA}_{\text{eff},H} + \frac{\kappa}{n_{\text{eff},H} + \kappa} \cdot 1.35\right),\; 1.00,\; 1.60\right)$$
       - Làm tròn `round(..., 4)` (hoặc `round(..., 2)` cho hiển thị, giữ `round(..., 4)` trên model).
4. **Áp dụng lên bản sao của `next_tasks` (BẤT BIẾN KHÔNG NHÂN ĐÔI BUFFER):**
   - Với mỗi `t` trong `next_tasks`:
     - Nếu `str(t.buffer_mode).strip().upper() == "NONE"`: giữ nguyên `buffer_mode="NONE", buffer_multiplier=1.0` (tôn trọng quyền tắt buffer riêng của task!).
     - Ngược lại:
       - **TUYỆT ĐỐI KHÔNG SỬA `t.duration_min`** (`t_new.duration_min == t.duration_min` 100%!).
       - Gán trên bản sao `t.model_copy(update=..., deep=True)`:
         - `buffer_mode = "COGNITIVE_LOAD"`
         - `alpha_light = alpha_c_light`
         - `alpha_heavy = alpha_c_heavy`
         - `buffer_multiplier = multiplier_for_load(t.cognitive_load, alpha_c_light, alpha_c_heavy)`
   - Đồng thời cập nhật `adapted_profile.buffer_mode = "COGNITIVE_LOAD"`, và đặt `adapted_profile.alpha_light` / `adapted_profile.alpha_heavy` bằng trung bình có trọng số (hoặc global shrinkage EWMA trên toàn bộ mẫu, kẹp `[1.00, 1.60]`).

---

#### Nhánh 2 — Học Nhịp Sinh Học Thực Tế Từ Mức Độ Bám Lịch (`Revealed vs. Stated Chronotype`, Giải quyết `Audit M-6`)
1. Với mỗi khung giờ $w \in \{\texttt{MORNING}, \texttt{AFTERNOON}, \texttt{EVENING}\}$:
   - Đếm tổng số ca được giao/ghi nhận trong khung $w$: $n_w$.
   - Tính $\text{AdherenceRate}(w) = \frac{\text{số ca adhered trong } w}{n_w} \in [0.0, 1.0]$.
   - Với các ca đã thực hiện (`est > 0, act > 0`) trong $w$, tính tốc độ hoàn thành trung bình $\overline{(d_{\text{est}} / d_{\text{act}})}_w$ (nếu không có ca nào hoàn thành trong $w$, đặt hệ số tốc độ $= 0.60$).
   - Khi $n_w \ge 2$ (`CHRONOTYPE_MIN_WINDOW_SAMPLES`):
     $$\text{Eff}(w) = \text{AdherenceRate}(w) \times \text{clip}\!\left(\overline{(d_{\text{est}} / d_{\text{act}})}_w,\; 0.60,\; 1.25\right)$$
2. Xác định khung giờ khai báo hiện tại `stated_pref`:
   - Chuẩn hóa từ `profile.focus_preference` (qua alias `EARLY_BIRD -> MORNING`, `NIGHT_OWL -> EVENING`, mặc định `"BALANCED"`).
   - Tìm khung $w^* = \arg\max_{w: n_w \ge 2} \text{Eff}(w)$ (nếu hòa thì ưu tiên giữ `stated_pref`).
3. **Điều kiện đổi nhịp sinh học an toàn:**
   - Nếu tồn tại $w^* \ne \text{stated\_pref}$ sao cho:
     - Trường hợp `stated_pref` là một buổi cụ thể (`MORNING`/`AFTERNOON`/`EVENING`) và $n_{\text{stated}} \ge 2$:
       $$\text{Eff}(w^*) - \text{Eff}(\text{stated\_pref}) \ge 0.22 \quad \text{VÀ} \quad \text{AdherenceRate}(\text{stated\_pref}) \le 0.75$$
     - Trường hợp `stated_pref == "BALANCED"` (hoặc buổi khai báo chưa có đủ 2 mẫu nhưng có ít nhất 1 buổi khác đạt $\text{Eff}(w^*) \ge 0.82$ vượt trung bình các buổi còn lại $\ge 0.22$): cũng cho phép đề xuất dịch sang $w^*$.
   - Khi thỏa điều kiện chuyển đổi sang $w^*$:
     - Cập nhật `adapted_profile.focus_preference = w_star`.
     - Xây dựng `CircadianEnergyProfile.from_preference(w_star)` và điền rõ `hourly_levels: Dict[int, int]` cho `h = 0..23` khớp với đường cong năng lượng mới (giữ nguyên mọi tinh chỉnh hợp lệ và đảm bảo khoảng giờ của $w^*$ đạt mức đỉnh `3`), gán vào `adapted_profile.energy_profile`.
     - Trên `adapted_tasks`: với các công việc nặng (`(t.cognitive_load or 2) >= 3` hoặc `t.priority >= 4`) mà người dùng **chưa khóa cứng khung giờ riêng** (`t.preferred_window in (None, "", "ANYTIME")`), gán `preferred_window = w_star`.

---

#### Nhánh 3 — Điều Nhịp Phục Hồi Sau Tuần Căng (`Pacing`) & Khoanh Vùng Sự Cố Lặp Lại (`Chronic Disruption Zones`, Giải quyết `Audit M-3` & `M-4`)
1. **Điều nhịp tách phiên (`Pacing Adaptation` — `Fix M-4`):**
   - Thu thập tất cả giá trị `fatigue_after` hợp lệ ($\in [0, 1]$) từ `timeline_logs` $\to$ tính `mean_fatigue` (nếu có).
   - Thu thập các ca dài (`planned_duration_min > 60` hoặc `estimated_duration_min > 60`): tính `long_overrun_rate` = tỷ lệ ca bị `actual_duration_min > planned_duration_min` (hoặc `actual_duration_min > estimated_duration_min * 1.15` hoặc `adhered == False`).
   - Nếu `(fatigue_samples and mean_fatigue > 0.65)` **HOẶC** `(len(long_blocks) >= 2 and long_overrun_rate >= 0.50)`:
     - Kích hoạt cờ `pacing_shifted = True`.
     - Với mọi công việc trong `adapted_tasks` có độ nặng `(t.cognitive_load or 2) >= 2` và `t.duration_min > 75` (trừ khi người dùng đã khóa cứng `is_splittable == False` tường minh trong `t.model_fields_set` và `t.work_rhythm not in ("FLOW", None)` — lưu ý: nếu `t.work_rhythm == "FLOW"` hoặc task mặc định chưa khóa chống tách, chuyển sang tách phiên vừa sức!):
       - Cập nhật tường minh qua `model_copy(update={"work_rhythm": "BALANCED", "min_chunk_min": 45, "max_chunk_min": 75, "is_splittable": True})`.
2. **Khoanh vùng sự cố lặp lại theo đúng Thứ trong tuần (`Chronic Disruption Zones` — `Fix M-3`):**
   - Quét trường `disruption_slot_window` trong `timeline_logs` (hỗ trợ các định dạng như `"Thursday 19:30-21:00"`, `"Thursday 19:00–21:00"`, hoặc dict `{"day_of_week": "Thursday", "start_time": "19:30", "end_time": "21:00"}`).
   - Gom cụm theo khóa `(day_of_week, hour_band_key)` — ví dụ quy tròn khung giờ về dải bắt đầu–kết thúc theo bội số 30/60 phút (hoặc giao của các khoảng trùng giờ trên cùng `day_of_week`, vd `("Thursday", "19:30", "21:00")`).
   - Nếu một vùng `(day_of_week, start_time, end_time)` xuất hiện **$\ge 2$ lần**:
     - Đưa vào danh sách trả về `chronic_disruption_zones`:
       ```python
       {
           "day_of_week": day,
           "start_time": start_hhmm,
           "end_time": end_hhmm,
           "occurrences": count,
           "action": "ADVISORY_BUFFER_ADDED" | "ADVISORY_WARNING_ONLY",
       }
       ```
     - **Kiểm tra an toàn tải $\rho \le 0.90$ trước khi chèn sự kiện đệm:** Ước tính nhanh tổng phút cần học của `adapted_tasks` chia cho tổng phút rảnh trong tuần của `adapted_profile`. Nếu $\rho_{\text{est}} \le 0.90$ và chưa có `FixedEvent` trùng giờ đó trên `day`, thêm vào `adapted_profile.fixed_events`:
       ```python
       FixedEvent(
           event_id=f"ADV_RESERVE_{day[:3].upper()}_{start_hhmm.replace(':', '')}",
           title=f"Khoảng đệm dự phòng phát sinh ({day} {start_hhmm}–{end_hhmm})",
           day_of_week=day,
           start_time=start_hhmm,
           end_time=end_hhmm,
           category="ADVISORY_BUFFER",
       )
       ```
     - **TUYỆT ĐỐI KHÔNG HẠ `hourly_levels`** cho sự cố đơn ngày!

---

### 2.4. Cấu Trúc Giá Trị Trả Về Của `adapt_preferences_for_next_week(...)`
Phải trả về dictionary chứa đầy đủ các khóa để cả `M4` (`handlers.py`), `M7` (`student_simulator` / E2E test), và `app.py` (`/api/workspace/adapt-next-week`) dùng trực tiếp:
```python
{
    "adapted_profile": adapted_profile,                  # CommitmentsProfile instance
    "adapted_commitments": adapted_profile.model_dump(), # Dict JSON-ready
    "adapted_tasks": adapted_tasks,                      # List[Task] instances
    "adapted_tasks_dump": [t.model_dump() for t in adapted_tasks],
    "category_alphas": {
        cat: {
            "sample_count": n_c,
            "ewma_ratio": round(ewma_c, 4),
            "alpha_light": round(a_light, 4),
            "alpha_heavy": round(a_heavy, 4),
        }
        for cat, ...
    },
    "window_effectiveness": window_stats_dict,           # MORNING / AFTERNOON / EVENING stats
    "preference_shifts": preference_shifts,              # List[Dict]: tiếng Việt thân thiện + mã Pattern P13
    "chronic_disruption_zones": chronic_zones,           # List[Dict]
    "pacing_adjusted": pacing_shifted,                   # bool
    "pattern_rules": [ ... ],                            # Trace chuẩn cho Pattern P13
}
```
Mỗi phần tử trong `preference_shifts` có dạng rõ ràng, không dùng tên biến kỹ thuật ở trường `message_vi`:
```python
{
    "shift_type": "CATEGORY_BUFFER" | "CHRONOTYPE_WINDOW" | "WORK_RHYTHM_PACING" | "CHRONIC_DISRUPTION_ZONE",
    "target": "CODING",
    "old_value": 1.35,
    "new_value": 1.41,
    "message_vi": "Nhóm việc CODING tuần trước thường cần thêm thời gian thực tế, hệ thống đề xuất nâng mức dự phòng lên +41% để tránh tràn lịch.",
    "pattern_id": "P13",
    "deterministic_rule": "alpha_hat = clip((n/(n+3))*EWMA + (3/(n+3))*alpha_0, 1.00, 1.60)",
}
```

---

## 3. ĐẶC TẢ CHI TIẾT FILE 2: CHỈNH SỬA `smartschedule/core/controller.py`

Mở [`smartschedule/core/controller.py`](../../../smartschedule/core/controller.py) và thực hiện **4 nâng cấp sạch sẽ, tương thích ngược 100%**:

### 3.1. Sửa `apply_estimate_buffer` & `annotate_estimate_buffer` (`Fix M-1` — Chống ghi đè xóa $\hat{\alpha}_{c,\ell}$ riêng từng môn & Lũy đẳng)
Tại dòng `104–164` của `controller.py`:
1. Viết hàm kiểm tra nhỏ ngay trong `ScheduleController`:
   ```python
   @staticmethod
   def _has_custom_task_cognitive_buffer(t: Task, profile: CommitmentsProfile) -> bool:
       if str(getattr(t, "buffer_mode", "HABIT")).strip().upper() != "COGNITIVE_LOAD":
           return False
       fields_set = getattr(t, "model_fields_set", set()) or set()
       if "alpha_light" in fields_set or "alpha_heavy" in fields_set:
           return True
       prof_l = float(getattr(profile, "alpha_light", 1.20))
       prof_h = float(getattr(profile, "alpha_heavy", 1.35))
       return abs(float(t.alpha_light) - prof_l) > 1e-6 or abs(float(t.alpha_heavy) - prof_h) > 1e-6
   ```
2. Trong `apply_estimate_buffer(cls, profile, tasks)` (cả ở nhánh `buf_mode == "COGNITIVE_LOAD"` LẪN nhánh `buf_mode == "HABIT"`!):
   - Nếu `str(getattr(t, "buffer_mode", "HABIT")).strip().upper() == "NONE"`: giữ nguyên `buffer_mode="NONE", buffer_multiplier=1.0`.
   - **Nếu `cls._has_custom_task_cognitive_buffer(t, profile)` là `True`:**
     Giữ nguyên `t.alpha_light` và `t.alpha_heavy` của riêng `t`! Chỉ cập nhật lại `buffer_multiplier = multiplier_for_load(t.cognitive_load, t.alpha_light, t.alpha_heavy)` để đảm bảo đồng bộ 100%.
   - Chỉ các task còn lại (chưa có hiệu chuẩn riêng theo môn) mới nhận `profile.alpha_light` / `profile.alpha_heavy` hoặc `multiplier_for_habit(habit)`.
3. Trong `annotate_estimate_buffer(cls, profile, buffered_tasks, out)`:
   - Đổi điều kiện thoát sớm ở dòng `151` từ:
     `if not habit and buf_mode != "COGNITIVE_LOAD": return`
     thành:
     `has_task_cog = any(str(getattr(t, "buffer_mode", "")).upper() == "COGNITIVE_LOAD" for t in buffered_tasks)`
     `if not habit and buf_mode != "COGNITIVE_LOAD" and not has_task_cog: return`

### 3.2. Thêm `ScheduleController.build_empty_current_week_profile(...)` (Yêu cầu gốc `M5.md` dòng 45)
- Import thêm `from datetime import datetime, timedelta, timezone` ở đầu `controller.py`.
- Viết classmethod:
  ```python
  @classmethod
  def build_empty_current_week_profile(
      cls,
      student_id: str = "STUDENT_USER",
      daily_start_time: str = "23:30",
      daily_end_time: str = "06:30",
      focus_preference: str = "BALANCED",
      estimate_habit: Optional[str] = "SOMETIMES",
      reference_dt: Optional[datetime] = None,
  ) -> CommitmentsProfile:
  ```
  - Tính múi giờ Việt Nam `tz_vn = timezone(timedelta(hours=7))`.
  - Lấy `now_dt = reference_dt.astimezone(tz_vn) if reference_dt else datetime.now(tz_vn)`.
  - Tính ngày Thứ Hai đầu tuần hiện tại: `monday_dt = (now_dt - timedelta(days=now_dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)`.
  - Kiểm tra an toàn giấc ngủ $\ge 6\text{h}$ (`360 phút` — `Pattern P6`): tính khoảng ngủ từ `daily_start_time` tới `daily_end_time` (xử lý qua nửa đêm `(end_min - start_min) % 1440`). Nếu `< 360` phút thì raise `ValueError("Thời lượng ngủ tối thiểu phải đạt từ 6 tiếng trở lên để đảm bảo sức khỏe.")`.
  - Trả về `CommitmentsProfile` hoàn toàn trống lịch cố định (`fixed_events=[]`, `personal_habits=[]`), `planning_week_start=monday_dt.isoformat()`, `now=now_dt.replace(second=0, microsecond=0).isoformat()`, **không đụng vào bất kỳ file JSON nào trong `data/presets/`**.

### 3.3. Thêm `ScheduleController.solve_adaptive(...)` (`Fix M-7` — Đồng bộ tự leo thang `SCORED_GREEDY -> HYBRID_ALNS`)
- **KHÔNG SỬA chữ ký mặc định `solve_schedule(..., algorithm: str = "EDF")`** để `Testing_System` và 195 test cũ không đổi dù chỉ 1 bit hash!
- Bổ sung thêm classmethod mới ngay cạnh `solve_schedule`:
  ```python
  @classmethod
  def solve_adaptive(
      cls,
      profile: CommitmentsProfile,
      tasks: List[Task],
      algorithm: Optional[str] = None,
      pinned_blocks: Optional[List[ScheduleBlock]] = None,
  ) -> Tuple[ScheduleOutput, TimeGridManager, bool]:
  ```
  - Nếu người dùng truyền tường minh một thuật toán cụ thể khác `SCORED_GREEDY` (ví dụ `"EDF"`, `"LST"`, `"WSPT"`, `"BACKTRACK"`, `"HYBRID_ALNS"`), chạy đúng thuật toán đó (`escalated = False`).
  - Nếu `algorithm` là `None`, `""`, hoặc `"SCORED_GREEDY"`:
    - Chạy `out, grid = cls.solve_schedule(profile, tasks, algorithm="SCORED_GREEDY", pinned_blocks=pinned_blocks)`.
    - Nếu `out.summary.tasks_unplaced > 0` và `"HYBRID_ALNS" in cls.SOLVER_REGISTRY` và `not (out.overload and out.overload.is_overloaded)`:
      - Chạy thử `alns_out, alns_grid = cls.solve_schedule(profile, tasks, algorithm="HYBRID_ALNS", pinned_blocks=pinned_blocks)`.
      - Nếu `alns_out.summary.tasks_unplaced < out.summary.tasks_unplaced` hoặc `alns_out.summary.deadline_satisfaction_rate > out.summary.deadline_satisfaction_rate`:
        trả về `(alns_out, alns_grid, True)`.
    - Trả về `(out, grid, False)`.

### 3.4. Thêm Helper Kiểm Tra Nhanh Công Thái Học Sau Sửa Cục Bộ (`inspect_repair_ergonomics` — Phục vụ `Fix M-8` cho Stage 2)
- Thêm 1 hàm tĩnh gọn trong `ScheduleController`:
  ```python
  @classmethod
  def inspect_repair_ergonomics(
      cls,
      profile: CommitmentsProfile,
      repair_out: Any,
  ) -> Dict[str, Any]:
  ```
  - Duyệt qua các block có trạng thái `"MOVED"` trong `repair_out.changes`: tìm block tương ứng trong `repair_out.schedule.blocks`.
  - Dùng `energy_prof = profile.get_energy_profile()` tính năng lượng trung bình `avg_e` trên các ô của block vừa bị dời.
  - Nếu block có `(b.cognitive_load or 2) >= 3` mà rơi vào đáy năng lượng (`avg_e <= 1.25`), ghi nhận vào danh sách `low_energy_heavy_moves`.
  - Trả về `{"has_ergonomic_degradation": bool(...), "low_energy_heavy_moves": [...], "unplaced_count": len(repair_out.schedule.unplaced_tasks)}`.

---

## 4. LỆNH KIỂM THỬ ĐỘC LẬP KẾT THÚC STAGE 1

Sau khi viết xong `cross_week_adapter.py` và sửa `controller.py`, chạy ngay lệnh sau:
```powershell
python -B -c "import ast; from pathlib import Path; imps=[n.module for n in ast.walk(ast.parse(Path('smartschedule/core/cross_week_adapter.py').read_text('utf-8'))) if isinstance(n, ast.ImportFrom) and n.module]; assert not any(x.startswith(('smartschedule.api','smartschedule.nlp','fastapi','smartschedule.core.storage','smartschedule.core.solvers')) for x in imps), imps; from smartschedule.core.cross_week_adapter import adapt_preferences_for_next_week; from smartschedule.core.controller import ScheduleController; p = ScheduleController.build_empty_current_week_profile(); print('STAGE 1 SMOKE OK:', p.planning_week_start)"
python -B -m pytest tests/logical/test_p2_alpha_calibration.py tests/architecture/ -q
```
Nếu cả 2 lệnh đều PASS 100%, đánh dấu `[x] DONE` ở đầu file này và trong [`M5_00_Master_Index.md`](./M5_00_Master_Index.md), rồi chuyển sang [`M5_02_Stage2_Disruption_Chat_LocalRepair.md`](./M5_02_Stage2_Disruption_Chat_LocalRepair.md).
