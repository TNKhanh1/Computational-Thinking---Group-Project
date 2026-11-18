# Kế Hoạch Hệ Thống Đánh Giá Chất Lượng & Năng Suất Lịch Trình (Tổng Hợp 9 Tài Liệu & Pipeline Test 2 Phần)

**Mục đích tài liệu này:**
1. **Đánh giá lại một cách thực tế và thẳng thắn** thiết kế cũ để loại bỏ tình trạng *nhồi nhét chỉ số*, loại các tiêu chí xung đột nội tại hoặc bất khả thi với dữ liệu hiện có, và tập trung đúng vào câu hỏi cốt lõi: **Lịch trình đầu ra có thật sự tạo ra Năng Suất (Productivity) và Bền Vững cho người học hay không?**
2. **Đặc tả chi tiết từng công thức, ý nghĩa nghiệp vụ, ngoại lệ biên và cơ chế ra kết luận**, bảo đảm **100% tiêu chí đều có nguồn gốc từ 8 tài liệu toàn văn** (`CI2009.pdf` là trang bìa 1 trang nên đóng góp `0` tiêu chí), không bịa ngưỡng tùy tiện.
3. **Thiết kế chi tiết hệ thống kiểm thử 2 phần khép kín** (tách khỏi cấu trúc file/thư mục cục bộ):
   $$\text{Phần 1: Gen Input phù hợp cho project} \longrightarrow \text{Chạy Project lấy Output} \longrightarrow \text{Phần 2: Đánh giá Output}$$

> **Nhật ký rà soát đối chiếu toàn văn paper (18/11/2026)** — các điểm đã sửa trong plan **và** trong `Testing_System/`:
> 1. **`P2.3` SJL làm sai phương pháp Smarr & Schirmer:** (a) gộp cả giờ `ACADEMIC_CLASS` vào hoạt động nên SJL bị thời khóa biểu chi phối; (b) lấy trung vị *tuyến tính* theo từng "ngày sinh học" tự đặt rồi lại lấy trung vị của các trung vị; (c) **đảo dấu** (non-class − class) nên lớp buổi sáng kéo pha sớm lại bị gắn nhãn `PHASE_DELAY`. Nay: sự kiện = block tự học, ngày lịch, trung vị **tròn** gộp theo loại ngày, $\text{SJL} = \phi_{\text{class}} - \phi_{\text{non-class}}$.
> 2. **Trọng số Corne `10:3:1` không có trong Schaerf** (chỉ ghi "descending order of weight", §4.2 tr. 25 — không phải tr. 28) $\rightarrow$ thay bằng vector so sánh từ điển.
> 3. **`P2.2`:** điều kiện `FLOW` / `≥ 90 phút` không có nguồn $\rightarrow$ chỉ xét `load = 3`; lớp học / sự kiện cố định ngay sau block **không** còn được tính là "nghỉ".
> 4. **Đã loại "Pre-Bedtime ≤ 60 phút"** (ngưỡng tự bịa; Kroese nói về đi ngủ muộn, mà `SLEEP` đã khóa cứng).
> 5. **`P4.2`:** bỏ cơ chế "lấy tạm 5 block đầu" tự chế; $\Delta t$ của Cowling & Johansson tính cả start **và** completion.
> 6. **`G2`:** slot đã `PINNED` nay bị trừ ở cả mẫu số của $\rho$.
> 7. **Bất biến Regime 2 / 4 / 6** được viết lại (bản cũ của Regime 2 luôn PASS; xem §4.3).
> 8. Sửa trích dẫn: Albulescu chỉ *gợi ý* nghỉ > 10 phút (không phải "bắt buộc"); "Conjecture 1" của Gombolay nói về hệ *embodied* — ý "ngập cảnh báo" nằm ở đoạn bàn luận tr. 137; Myers không có thang `1–5 ⭐` và không cho ngưỡng `LOW/MEDIUM/HIGH`.
> 9. `Testing_System` import nhầm tên package `schedule_testing_system` (thư mục thật là `Testing_System`) nên không chạy được — đã sửa.

---

## 1. Tự Kiểm Điểm: Bản Sơ Thảo Trước Bị Nhồi Nhét Gì & Sửa Thế Nào Để Đo Đúng *Productivity*?

### 1.1. Bốn điểm bất cập trong cách gom 24 tiêu chí dàn phẳng trước đây
Nếu giữ nguyên 24 mã tiêu chí (~45+ con số con) ở cùng một cấp độ, hệ thống đánh giá sẽ gặp **4 vấn đề thực tế**:
1. **Nhồi nhét chỉ số trùng lặp & đối nghịch nhau:**
   - **Ví dụ 1 — `Makespan (C_max)` chống lại `Spreading` và `Circadian Peak`:** Trong lập lịch xưởng máy (`Vieira`), giảm $C_{\max}$ (xong toàn bộ lô hàng càng sớm càng tốt) là tốt. Nhưng với lịch học cá nhân 7–14 ngày, ép $C_{\max}$ nhỏ đồng nghĩa khuyến khích **nhồi hết bài sang Thứ Hai–Thứ Ba**. Điều này trực tiếp phá hủy chỉ số **dàn tải theo ngày (`Colorni`, `Gombolay tr. 143`)**, gây cụm **`>2` phiên nặng/ngày (`Corne`)**, và ngăn cản việc **chờ tới giờ đỉnh năng lượng ngày hôm sau (`Smarr & Schirmer`, `Gombolay strategic idling`)**. Vì vậy, loại bỏ tối ưu $C_{\max}$ khỏi bộ tiêu chí cốt lõi, giữ **Onset Timeliness** (tránh trì hoãn khởi phát vô lý) thay cho việc ép xong dồn đầu tuần.
   - **Ví dụ 2 — `Lateness L_max` hiểu sai cơ chế Solver của SmartSchedule:** Solver của SmartSchedule luôn ép `end_slot <= deadline_slot` và đẩy phần không kịp vào `unplaced_tasks`, nên $L_{\max}$ của các block do solver đặt không bao giờ dương ($L_i > 0$ chỉ xảy ra nếu người dùng tự kéo thả vi phạm `H4`). Do đó, phần không kịp hạn phải đo qua **Giá trị ưu tiên bị rơi (`unplaced_tasks`)**, còn các block đã đặt đúng hạn cần đo **Deadline Slack Margin** (khoảng dư an toàn trước hạn), không đánh tráo bằng khái niệm trễ dây chuyền kiểu xưởng sản xuất.
   - **Ví dụ 3 — Trộn "chỉ số chẩn đoán kỹ thuật" với "chỉ số năng suất":** `fragmentation_index` hiện đếm các khe `FREE` lẻ `<30 phút`, nhưng chính khoảng nghỉ 15 phút (`REST`) và buffer phòng vệ lại tạo ra các khoảng cách ngắn giữa các block. Đặt `fragmentation_index` ngang hàng với tiêu chí chính sẽ gây nhiễu khi chấm điểm.
2. **Đưa vào chỉ số không chạy được trong kiểm thử tự động một lần (*Single-run Evaluation*):**
   - `SAGAT` (Situational Awareness), tỷ lệ người dùng chấp nhận/từ chối gợi ý (`Type I / Type II` compliance), hay đánh giá hài lòng `1–5 ⭐` (thang đo do Project tự đặt; `Gombolay Ch. 5–6` dùng Likert) cần **tương tác nhiều phiên với người dùng thật**. Đưa chúng vào phần chấm một cặp `(input, output)` hay vào vòng lặp `Gen Input -> Run -> Evaluate` là bất khả thi. Chúng phải được tách sang **nhánh theo dõi dài hạn (Longitudinal UX Track)**, chỉ giữ **kiểm tra bảo toàn các block `PINNED`** trong phần đánh giá tự động.
3. **Ngộ nhận giữa "Vẽ kín lịch" (`% scheduled = 100%`) và "Năng suất thật sự" (*Productivity*):**
   - Một lịch xếp kín 85% thời gian thức, nhét 4 phiên nặng vào một ngày mệt mỏi, cắt sạch khoảng nghỉ 15 phút và không chừa 1 chút buffer nào vẫn đạt **`% scheduled = 100%`**, nhưng khi thực thi thực tế chỉ cần một bài phát sinh 20% thời gian là toàn bộ lịch vỡ dây chuyền và người học kiệt sức.
   - **Năng suất thực chất = Làm đúng việc giá trị cao $\times$ Đúng giờ não tỉnh táo nhất $\times$ Nhịp độ bền vững có phục hồi $\times$ Chịu được sai số thực tế mà không gãy kế hoạch.**
4. **Thiếu phép thử "Chạy qua biến động" (Robustness-Adjusted Productivity):**
   - Không chỉ chấm bản vẽ tĩnh, bộ đánh giá cần **cho lịch chạy thử qua bộ sốc thời lượng (`+25% / +50%`)** để trả lời câu hỏi thực dụng nhất: *Nếu mọi thứ ngoài đời diễn ra chậm hơn dự kiến một chút, bao nhiêu `%` công việc giá trị cao trên lịch này vẫn sống sót đúng hạn?*

### 1.2. Kiến trúc tái cấu trúc theo Mô hình 3 Tầng (Gọn, Có Trọng Tâm, Không Nhồi Nhét)

Thay vì 24 tiêu chí dàn phẳng, toàn bộ tiêu chí từ 8 paper được tinh lọc thành **3 tầng rành mạch**:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ TẦNG 0: CỔNG KHẢ THI & BỐI CẢNH ĐẦU VÀO (Bắt buộc kiểm tra trước tiên)     │
│   • G1: Hard Feasibility & Pin Integrity (H1-H5 + start_after + splitting) │
│   • G2: Input Tightness Context (Tỷ lệ tải ρ để biết input dễ hay quá tải) │
├────────────────────────────────────────────────────────────────────────────┤
│ TẦNG 1: 4 TRỤ CỘT ĐO ĐÚNG PRODUCTIVITY (9 Chỉ Số Cốt Lõi Quyết Định)       │
│   • P1 Value & Timeliness: (P1.1) Giá trị Deadline giữ được;               │
│                            (P1.2) Chống trì hoãn khởi phát & dồn <10h      │
│   • P2 Brain & Biology:    (P2.1) Việc nặng đúng Peak & tránh ép cú đêm;   │
│                            (P2.2) Nghỉ >10p sau việc nặng;                 │
│                            (P2.3) Pha tròn Social Jetlag & Ổn định pha     │
│   • P3 Sustainable Pacing: (P3.1) Dàn tải đều tuần & tránh quá tải cực đoan│
│                            (P3.2) Tránh dồn >2 nặng/ngày, kẹp bữa, đổi ngữ cảnh
│   • P4 Real-World Survival:(P4.1) Buffer thực & % giá trị SỐNG SÓT sau sốc │
│                            (P4.2) Độ ổn định sau sửa D(π0,π1), Eq 1st, Δt  │
├────────────────────────────────────────────────────────────────────────────┤
│ TẦNG 2: GIẢI THÍCH, ĐỐI CHIẾU SOLVER & THEO DÕI NGƯỜI–MÁY DÀI HẠN          │
│   • D1: Top 3-5 Cảnh báo ICEE (chỉ lỗi thật, không spam cảnh báo nhiễu)    │
│   • D2: Đối chiếu chéo đa solver theo Thứ tự Từ Điển + Chẩn đoán phụ       │
│   • D3: Nhánh Longitudinal UX (1-5 sao, Type I/II, SAGAT — tách khỏi test) │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Kiểm Kê Nguồn Gốc Từ 9 Tài Liệu (Truy Xuất Đúng Tầng & Không Bịa Ngưỡng)

| STT | Tài liệu | Tác giả / Năm | Phạm vi đọc | Đóng góp chính xác & Tầng áp dụng |
|---|---|---|---|---|
| 1 | `download.pdf` | **A. Schaerf (1999)** — *A Survey of Automated Timetabling* | 42 trang toàn văn | Hard/Soft constraints & Distance to Feasibility (§1.2, tr. 2 $\rightarrow$ `G1, P1.1`); phê phán `% scheduled` & tổng trọng số mờ (§5.1, tr. 29 $\rightarrow$ `G2, D2`); Period desirability `Junginger` (tr. 8), `De Werra` (tr. 16 $\rightarrow$ `P2.1`); Weekly spreading `Colorni` (tr. 8), `Papoulias` (tr. 10 $\rightarrow$ `P3.1`); Clustering & Meal boundary `Corne et al. 1993` — 3 mức phạt *theo thứ tự trọng số giảm dần, không có giá trị số* — `Carter` & `Laporte & Desroches` (§4.2, tr. 25 $\rightarrow$ `P3.2`); Relaxation warnings `Yoshikawa COASTOOL` (§2.3, §2.5.7 tr. 8, 13 $\rightarrow$ `D1`); Đối chiếu tương đối (§7.3–7.5 tr. 33–34 $\rightarrow$ `D2`) |
| 2 | `An_Intelligent_Personal_Assistant_for_Task_and_Tim.pdf` | **K. Myers et al. (2006)** — *PExA / CALO* | 19 trang toàn văn | `SPARK` feasibility (tr. 5 $\rightarrow$ `G1`); `PTIME` SCSP ưu tiên đa tiêu chí, `fragmentation`, `stability` (tr. 6, 8 $\rightarrow$ `P4.2, D2`); `EMP` rủi ro hoàn thành khi thiếu đệm (tr. 6–7 $\rightarrow$ `P4.1`); `ICEE` truy xuất nguyên nhân & cảnh báo (tr. 9–10 $\rightarrow$ `D1`); `Towel UI` relaxation warnings & `Rescheduling Effort high/medium/low` (tr. 13 — paper **không** cho ngưỡng, nên dải `LOW/MEDIUM/HIGH` là tham số Project $\rightarrow$ `P4.2, D1`); người dùng ít chịu được gợi ý kém (tr. 9 $\rightarrow$ `D3`) |
| 3 | `Rescheduling_Manufacturing_Systems_A_Framework_of_.pdf` | **G. E. Vieira, J. W. Herrmann & E. Lin (2003)** (*J. Scheduling*, 6:39–62) | 24 trang toàn văn | Hoàn thành giá trị & sản lượng mục tiêu `Shafaei & Brunn` (tr. 47–48) & `Portougal & Robb` (tr. 57–58 $\rightarrow$ `P1.1`); `Setup / Context-switching` (tr. 48 $\rightarrow$ `P3.2`); `Mehta & Uzsoy` protective buffer (tr. 53, 56), `Daniels & Kouvelis` & `Herrmann` worst-case (tr. 45, 53), `O'Donovan` realized vs planned (tr. 53 $\rightarrow$ `P4.1`); Phân biệt `Stability / Nervousness / Robustness` qua `Cowling & Johansson` (tr. 46), `Wu et al.` (tr. 47), `Bean et al.` (tr. 48), `Wu & Li` (tr. 50 $\rightarrow$ `P4.2`); Computational time (tr. 48 $\rightarrow$ `D2`) |
| 4 | `CI2009.pdf` | **I. Refanidis & A. Alexiadis (2009)** — *SelfPlanner* | 1 trang bìa thư mục + URL handle | **`0` tiêu chí được trích** (thiếu toàn văn để kiểm chứng; tuyệt đối không suy diễn) |
| 5 | `Plan_Stability_Replanning_versus_Plan_Repair.pdf` | **M. Fox, A. Gerevini, D. Long & I. Serina (2006)** | 10 trang toàn văn | **Symmetric Plan Difference** $D(\pi_0, \pi_1)$ trên phần chưa thực thi (§2, §3 Def. 2–3, tr. 2–3 $\rightarrow$ `P4.2`); Đo giữ nguyên bước cận kề `Eq 1st`, `Orig`, `Diff` (§5.2, tr. 9 $\rightarrow$ `P4.2`); Thiết kế sinh nhiễu biến thiên cấp độ có hệ thống (§5.1, tr. 5 $\rightarrow$ `Regime 6`) |
| 6 | `journal.pone.0272460.pdf` | **P. Albulescu et al. (2022)** (*PLOS ONE*, 17:8) | 27 trang toàn văn | Meta-analysis ($N=2335, k=22$): Vigor $d=.36, p<.001$; Fatigue $d=.35, p<.001$; Thời lượng nghỉ $b=.07, p=.006, R^2=.34$; Hiệu năng tổng thể **không** có ý nghĩa ($d=.16, p=.116$); **Phát hiện lõi cho tác vụ nhận thức (`Table 5`, tr. 1, 15):** micro-break $\le 10$ phút không cải thiện hiệu năng sau tác vụ nhận thức (`k=9, d=-.09, p=.541`); tác giả *gợi ý* "recovering from highly depleting tasks may need more than 10-minute breaks" $\rightarrow$ ngưỡng **$> 10$ phút** ($\rightarrow$ `P2.2`, chỉ áp cho `cognitive_load == 3`); khoảng `2 phút–4h` (tr. 8) chỉ là **phạm vi thời gian làm việc trong các nghiên cứu gốc**, không phải ngưỡng khuyến nghị |
| 7 | `34_Million_real-world_learning_management_system_l.pdf` | **B. L. Smarr & A. E. Schirmer (2018)** (*Scientific Reports*, 8:4793) | 10 trang toàn văn | Dữ liệu `14,894` sinh viên, `3.4 triệu` LMS logins: `Larks / Finches / Owls`; **Social Jetlag (SJL)** = trung vị pha tròn (giờ đồng hồ $\rightarrow 2\pi$ radian) của *hoạt động học* ngày có lớp **trừ** ngày không lớp, gộp toàn bộ sự kiện theo loại ngày (Methods tr. 8; mốc thực nghiệm `60%` sinh viên có SJL `> 30 phút`, tr. 6); sớm pha (*advance*) vào ngày học tương quan âm với GPA mạnh hơn trễ pha, *Owl* bất lợi ở mọi khung giờ (tr. 5–6 $\rightarrow$ `P2.1, P2.3`); *internal desynchrony* do lịch bất ổn chỉ là **giả thuyết** ở phần Discussion (tr. 6) $\rightarrow$ chỉ dùng làm chẩn đoán phụ |
| 8 | `fpsyg-09-00746.pdf` | **F. Svartdal, S. Granmo & F. S. Færevaag (2018)** (*Frontiers in Psychology*, 9:746) | 11 trang toàn văn | `N=965`, 5 studies: **Implemental Onset Delay** (`Steel`, `Moon`, `Senécal` Table 1 tr. 2–3 — tác vụ khó bị né nhất); **Preparatory behavior** (`Studies 3a–3b`, tr. 7–9); **Phần lớn bài nộp `< 10h` trước hạn** (`Howell 2006`, Table 2 tr. 4 $\rightarrow$ `P1.2`). *Bedtime procrastination* (`Kroese`) chỉ mô tả việc **đi ngủ muộn hơn dự định** — SmartSchedule đã khóa cứng `SLEEP` (`H2`) nên **không** suy ra được tiêu chí "việc nặng ≤60p trước giờ ngủ" (đã loại) |
| 9 | `1010803411-MIT.pdf` | **M. C. Gombolay (2017)** (MIT PhD Thesis) | 218 trang toàn văn | Ràng buộc cận trên/dưới (§3.2.1 tr. 78–80 $\rightarrow$ `G1`); Phân loại nút thắt input (§3.4.1 tr. 96–98 $\rightarrow$ `G2`); **Strategic idling** (tr. 92–93 $\rightarrow$ `P1.2`); Tương tác phi tuyến Workload/Utilization & Preferences (§2.5.4 tr. 70, Ch. 6 tr. 146, 164–182: *extremely high vs low utilization* tr. 181 $\rightarrow$ `P3.1`); Phân biệt lịch khả thi nhưng chất lượng kém (§5.3 tr. 131 $\rightarrow$ `D2`); Không ngập cảnh báo (nhận xét về "deluge of false alarms and non-critical alerts" trong phần bàn luận quanh `Conjecture 1`, tr. 137 — bản thân Conjecture 1 nói về hệ thống *embodied* $\rightarrow$ `D1`; con số `Top 3–5` là tham số Project); Giải thích lựa chọn (§7.2.1 tr. 189 $\rightarrow$ `D1`); Mixed-initiative `Sheridan 4–6`, `Type I/II`, `SAGAT Eq. 6.1–6.2`, `Berry 60%` (tr. 58, 72, 126–136, 148–185 $\rightarrow$ `D3` & bảo toàn `PINNED`) |

**Nguyên tắc tách biệt Bất Di Bất Dịch:**
- Mọi ngưỡng trích dẫn (`> 10 phút` nghỉ của Albulescu, `> 30 phút` SJL của Smarr & Schirmer, `< 10h` của Howell/Svartdal, `> 2 bài/ngày` và **thứ tự** trọng số giảm dần của Corne, `60%` acceptance của Berry/PTIME qua Gombolay) đều là **số liệu trích từ paper**. Schaerf **không** công bố trọng số số học cho Corne, nên bản cũ ghi `10:3:1` là bịa — đã thay bằng so sánh **từ điển** (vector 3 phần tử).
- Các tham số thử nghiệm như mức sốc thời lượng **`+25%` / `+50%`**, phân ngưỡng tải sinh test **$\rho$**, cửa sổ "initial actions" của Fox (`24h`), dải `LOW/MEDIUM/HIGH` của Towel UI, ngân sách `Top 3–5` ICEE, khoảng cách `≤ 1 slot` = "liền kề" (Corne), `≤ 2 slot` = cặp chuyển ngữ cảnh, và các ngưỡng chính sách trong `EvaluationConfig` đều là **Tham số cấu hình của Project**, tách khỏi chân lý bài báo và hoàn toàn chỉnh được.

---

## 3. Đặc Tả Chi Tiết Công Thức & Cách Hoạt Động Của 3 Tầng Đánh Giá

> **Quy ước phạm vi dữ liệu trước khi tính mọi chỉ số:**
> 1. Bắt buộc chuẩn hóa tập công việc qua đúng 2 bước tiền xử lý giống hệt luồng giải của SmartSchedule: **`expand_personal_habits(profile, tasks)` $\rightarrow$ `apply_estimate_buffer(profile, expanded_tasks)`**. Chỉ sau bước này `get_planned_duration_min()` mới phản ánh đúng thời lượng kế hoạch thực tế (`planned_duration_min`, kể cả khi `Task` thô chưa gán sẵn `buffer_mode` hay `buffer_multiplier` từ `profile`).
> 2. Tầm nhìn đánh giá là **`horizon_slots` thực tế** (từ `7 ngày = 672 slot` tới `14 ngày = 1344 slot` hoặc mở rộng tới deadline xa nhất trong tuần), **không bao giờ cắt cứng tại `672` slot** khi có lịch 2 tuần.

### 3.1. Tầng 0 — Cổng Khả Thi & Bối Cảnh Đầu Vào (`G1`, `G2`)

#### `G1` — Hard Feasibility & Pin Integrity ($C_{\text{hard}}$)
*(Schaerf §1.1–1.2; Myers SPARK; Gombolay §3.2.1, Ch. 5–6)*
- **Cách đo:** Kết hợp bộ kiểm tra có sẵn `audit_hard_constraint_violations` (cho $H_1$: đè `OCCUPIED`, $H_2$: đè `SLEEP`, $H_3$: đè block khác, $H_4$: vượt deadline, $H_5$: vi phạm `depends_on`, và vượt biên `[0, horizon_slots)`) **cộng thêm 5 điều kiện kiểm tra bổ sung**:
  1. `start_after`: Mọi block (trừ `DONE` hoặc block `PINNED` hợp lệ do người dùng chủ động ghim sớm) phải thỏa `start_slot >= resolve_start_after_slot()`.
  2. `now_slot`: Mọi block không ở trạng thái `DONE` hay `PINNED` không được đặt lấn về quá khứ trước `now_slot`.
  3. Quy tắc tách mảnh & thứ tự chunk: Nếu `is_splittable == False` thì `total_chunks == 1`; mọi mảnh của cùng task phải tăng dần không chồng chéo (`chunk k end <= chunk k+1 start`), và (ngoại trừ block `PINNED`/`DONE` hoặc sau xử lý `overrun`) không mảnh nào vượt quá `max_chunk_min` (trường hợp chia không bội đủ `min_chunk_min` được tính theo đúng quy tắc chia đều + dồn 1 slot dư lên các mảnh đầu của bộ chia SmartSchedule).
  4. Đủ thời lượng: Tổng thời lượng các block đã xếp của mỗi task có mặt trong lịch phải bằng `get_planned_duration_min()`.
  5. **Pin Integrity (`Gombolay Mixed-Initiative`):** Với mỗi block `PINNED` hợp lệ trong đầu vào (không tự đè `SLEEP`/`OCCUPIED`/vượt deadline), lịch đầu ra phải giữ nguyên `(task_id, start_slot, end_slot)`.
- **Ý nghĩa:** Nếu `G1 > 0`, lịch **thất bại ngay lập tức (`INVALID`)** bất kể các điểm còn lại cao đến đâu.

#### `G2` — Structural Load Context ($\rho$, Tightness & Bottleneck)
*(Schaerf §5.1 phê phán `% scheduled`; Gombolay §3.4.1 phân loại nút thắt)*
- **Công thức:**
  $$\rho = \frac{\sum_{t \in T_{\text{valid}}} \big(\text{planned\_slots}(t) - \text{pinned\_slots}(t)\big)}{\text{usable\_free\_slots}_{\text{sau khi đặt PINNED}}([\text{now\_slot}, \min(\max_t d_t, \text{horizon\_slots})])}$$
  *(Slot đã ghim bị trừ ở **cả tử và mẫu** — bản cũ chỉ trừ ở tử nên coi slot đã ghim là sức chứa rảnh, làm $\rho$ thấp giả.)* Đồng thời báo tách riêng tải bắt buộc $\rho_{\text{deadline}}$ (chỉ tính `DEADLINE`) và tải linh hoạt `HABIT`. Quá tải cấu trúc $\iff \rho > 1$ **hoặc** $\rho_{\text{deadline}} > 1$ **hoặc** kiểm tra sức chứa theo từng mốc hạn (`check_deadline_capacity`) báo thiếu.
- **Ý nghĩa & Giá trị thực tiễn:**
  - Nếu $\rho > 1.0$: đầu vào bị **quá tải cấu trúc (*Capacity Shortage*)**. Nhiệm vụ của solver lúc này là **giữ lại tối đa việc giá trị cao (`P1.1`)**, không bị đánh giá là "lỗi thuật toán không xếp hết việc".
  - Nếu $\rho \le 1.0$ mà vẫn rơi việc hoặc xếp kém: lộ rõ **nghẽn do phân mảnh hoặc thuật toán kém (*Fragmentation / Algorithm Bottleneck*)**.

---

### 3.2. Tầng 1 — 4 Trụ Cột Đo Đúng *Productivity* (`P1`–`P4`)

#### TRỤ CỘT P1 — Effective Value Delivery *(Làm đúng việc quan trọng, đúng thời điểm)*

##### `P1.1` — Priority-Weighted On-Time Value & Distance to Feasibility
*(Vieira — Shafaei & Brunn tr. 47–48, Portougal & Robb tr. 57–58; Schaerf §1.2 tr. 2)*
- **Công thức:** Gọi $T_D$ là tập tác vụ có hạn chót (`DEADLINE`, `deadline_slot is not None`).
  $$\text{ValueRate}_{D} = 100 \times \frac{\sum_{t \in T_D^{\text{ok}}} t.\text{priority}}{\sum_{t \in T_D} t.\text{priority}} \quad (\%), \qquad \text{MissedPriority} = \sum_{t \in T_D \setminus T_D^{\text{ok}}} t.\text{priority}$$
  Kèm **Distance to Feasibility**: `(unplaced_deadline_count, unplaced_deadline_min)` và **Min/Mean Deadline Slack Margin**:
  $$\text{SlackMargin}_i = (\text{deadline\_slot}_i - \text{last\_end\_slot}_i) \times 15 \text{ phút}$$
  Tỷ lệ hoàn thành thói quen `HABIT` (`PersonalHabit` / task không hạn) báo riêng ở chỉ số phụ (`HabitValueRate`), tránh việc xếp xong 5 thói quen `priority=1` làm che lấp chuyện bỏ rơi 1 đồ án `priority=5`.
- **Vì sao phản ánh đúng Productivity:** Giả sử sinh viên có 1 bài tập lớn (`priority=5`, 180 phút) và 4 việc nhỏ (`priority=1`, mỗi việc 30 phút). Nếu solver chỉ đặt vừa 4 việc nhỏ và bỏ bài lớn, cách đếm cổ điển (`% scheduled`) vẫn báo **`80%`**, tạo ảo giác năng suất cao; nhưng `P1.1` báo ngay **`44.4%` (`4 / 9 điểm giá trị`)** và mất `priority=5`.

##### `P1.2` — Anti-Procrastination, Onset Timeliness & Unjustified `<10h` Crowding
*(Svartdal et al. 2018 tr. 2–9; Gombolay tr. 92–93 strategic idling)*
- **Công thức (áp dụng trên tác vụ $t \in T_D$ đã xếp có cửa sổ sẵn sàng hợp lệ):**
  1. Gọi mốc sẵn sàng thực tế của $t$:
     $$r_t = \max\big(\text{now\_slot},\; \text{start\_after\_slot}(t),\; \max_{p \in \text{depends\_on}(t)} \text{last\_end\_slot}(p)\big)$$
     Cửa sổ khả dụng $W_t = (\text{deadline\_slot}_t - r_t) \times 15$ phút.
  2. **Implemental Onset Delay Rate** (đặc biệt soi nhóm `cognitive_load == 3` vì dễ bị né tránh nhất theo `Svartdal Table 1`):
     $$\text{OnsetDelay}_t = \frac{(\text{first\_start\_slot}_t - r_t) \times 15}{W_t}$$
  3. **Preparatory Chain Margin** (*Svartdal Studies 3a–3b*): với cặp $(p \rightarrow t)$ có `depends_on`, đo khoảng đệm hoàn thành trước hạn $(\text{last\_end\_slot}_p \rightarrow \text{deadline\_slot}_t)$ xem bước tiền đề có bị đẩy sát nút gây dồn ép dây chuyền không.
  4. **Unjustified Last-10h Crowding (`Howell 2006 <10h`, Table 2 tr. 4):** Chỉ xét các task có $W_t > 600$ phút (`10 giờ`) để tránh phạt oan bài giao gấp. Nếu có block của $t$ nằm trong đoạn `[deadline_slot_t - 40, deadline_slot_t)`, kiểm tra xem ở khoảng sớm hơn trước đó có slot `FREE` liên tục đủ chỗ và không kém năng lượng hay không. Nếu **có chỗ trống hợp lệ trước đó mà vẫn đẩy dồn vào `< 10h`**, tính tỷ lệ phút dồn bất hợp lý; ngược lại **miễn phạt** nếu trễ khởi phát dùng để:
     - Đợi khung năng lượng cao hơn (`energy_level == 3` hoặc `preferred_window`) trong ngày đầu tiên khả dụng (*Smart Circadian Deferral*), hoặc
     - Chừa khe ghép một task gấp khác / bảo toàn thứ tự hợp lý (**Strategic Idling**, `Gombolay tr. 92–93`).
- **Vì sao phản ánh đúng Productivity:** Hai lịch đều xong 100% trước hạn (`P1.1 = 100%`), nhưng Lịch A bắt đầu đồ án `load=3` ngay buổi sáng sẵn sàng đầu tiên có Peak; Lịch B trì hoãn để 2 tiếng cuối trước hạn mới nhồi. Lịch B có rủi ro bỏ cuộc / chất lượng bài làm thấp cực cao dù nhìn bề mặt vẫn tưởng đạt hết deadline.

---

#### TRỤ CỘT P2 — Cognitive Power & Biological Alignment *(Não tỉnh đúng lúc, có nghỉ đúng ngưỡng, không lệch nhịp sinh học)*

##### `P2.1` — Heavy-Task Circadian Alignment & Forced Phase-Advance Risk
*(Schaerf — Junginger, De Werra; Smarr & Schirmer 2018 tr. 5–6)*
- **Công thức:**
  1. **Heavy Peak Match Rate (Riêng cho `cognitive_load == 3`):**
     $$\text{HeavyPeakPct} = 100 \times \frac{\text{Tổng phút block (load = 3) nằm ở slot có } \text{energy\_level} = 3}{\text{Tổng phút mọi block có } \text{load} = 3}$$
     *(Lưu ý: giữ tách bạch khỏi `deep_peak_match_pct` hiện có của project vốn gộp từ `load >= 2`, vì làm việc sâu thực sự cần đo chuẩn `load == 3`.)*
  2. **Preferred Window Match Rate:** `%` phút của các block thuộc task có khai báo `preferred_window` (`MORNING` / `AFTERNOON` / `EVENING`, không tính `ANYTIME`) nằm đúng vào khung giờ tương ứng.
  3. **Forced Phase Advance Count (`Smarr & Schirmer tr. 5`):** Đếm số block (không tính block `PINNED`/`DONE`) có `cognitive_load == 3` của người có profile `EVENING` (*Owl*) bị xếp giao với khung sáng `MORNING` `06:00–12:00` (`slot_in_day ∈ [24, 48)`, vùng có `energy_level == 1` trong mô hình circadian của SmartSchedule) **trong khi từ thời điểm sẵn sàng tới trước hạn vẫn còn khung `AFTERNOON`/`EVENING` đủ rộng ở mức năng lượng cao hơn (`>= 2` hoặc `3`)**.
- **Vì sao phản ánh đúng Productivity:** Theo *Smarr & Schirmer*, nhóm *Owls* bị ép làm bài kiểm tra vào sáng sớm chịu **mức suy giảm điểm nặng nhất**. Một thuật toán *Energy-Blind* (như `EDF` thuần) luôn có xu hướng quét từ 07:00 sáng và phạm đúng lỗi này — `P2.1` bắt trúng điểm yếu đó.

##### `P2.2` — Cognitive Recovery Break Compliance & Continuous Time-on-Task
*(Albulescu et al. 2022 Abstract tr. 1, Results tr. 15, Table 5)*
- **Công thức:** Với mỗi block **`cognitive_load == 3`** (trừ `DONE`) — *chỉ load = 3, vì phát hiện null-effect của Albulescu là cho tác vụ trước nghỉ thuộc loại **cognitive**; các điều kiện `work_rhythm == "FLOW"` hay `≥ 90 phút` ở bản cũ không có nguồn trong paper nên đã loại*:
  - Kiểm tra slot ngay sau `end_slot` có phải **slot không mang tải công việc** hay không: `FREE`/`REST`, `MEAL` hoặc `SLEEP` (hoặc hết horizon). **Không** tính là nghỉ nếu slot đó là block học khác, `ACADEMIC_CLASS` hay `FixedEvent`/sự cố khác — chuyển thẳng sang lớp học không phải là "tách khỏi công việc". 1 slot = 15 phút $> 10$ phút.
  - Tính:
    $$\text{HeavyRecoveryRate} = 100 \times \frac{\text{Số block load=3 có slot nghỉ ngay sau}}{\text{Tổng số block load=3}} \quad (\%)$$
    và **Max Uninterrupted Stretch (phút)** (chẩn đoán phụ): chuỗi slot `BLOCK` nối liền nhau dài nhất. Khoảng `2 phút–4h` trong paper chỉ là phạm vi dữ liệu, **không** dùng làm ngưỡng.
- **Vì sao phản ánh đúng Productivity:** Albulescu (`N=2335, k=22`): micro-break tăng sinh lực ($d=.36$), giảm mệt mỏi ($d=.35$) nhưng **không** tăng hiệu năng tổng thể ($d=.16, p=.116$); riêng sau tác vụ nhận thức, nghỉ $\le 10$ phút cho $d=-.09, p=.541$; thời lượng nghỉ dài hơn tăng hiệu năng ($b=.07, p=.006$) và tác giả *gợi ý* cần nghỉ $> 10$ phút. Khi solver kích hoạt `Crunch Tier 1` cắt nghỉ 15 phút để cứu việc có hạn, `P2.2` hạ mức thành cảnh báo (`WARNING`); ngoài trường hợp đó là lỗi nghiêm trọng.

##### `P2.3` — Circular Social Jetlag (SJL) *(+ chẩn đoán phụ: độ phân tán pha giữa các ngày)*
*(Smarr & Schirmer 2018 — Results tr. 4–6, Methods tr. 8)*
- **Làm đúng phương pháp của paper (Methods tr. 8):**
  1. **Sự kiện hoạt động** = các slot `BLOCK` tự học (tương đương *LMS login* trong paper). `ACADEMIC_CLASS` **chỉ dùng để phân loại ngày**, không đưa vào làm sự kiện hoạt động — nếu gộp cả giờ lớp (như bản cũ), SJL bị thời khóa biểu cố định chi phối và không còn đo được bộ xếp lịch (Regime 3 seed 42: bản cũ ra `600 phút`, bản đúng ra `75 phút`).
  2. **Phân loại ngày theo ngày lịch** (`slot // 96`): *ngày có lớp* = ngày có ≥ 1 buổi `ACADEMIC_CLASS`; *ngày không lớp* = còn lại. Chỉ xét ngày có ≥ 1 slot tự học. Trả `N/A` nếu thiếu một trong hai loại ngày.
  3. Đổi giờ đồng hồ của mỗi slot (lấy tâm slot) sang góc $\theta = 2\pi \cdot \frac{m}{1440}$ và lấy **trung vị tròn gộp toàn bộ sự kiện** của mỗi loại ngày ($\tilde{\phi}_{\text{class}}, \tilde{\phi}_{\text{non-class}}$) — trung vị tròn = điểm cực tiểu tổng khoảng cách tròn, như toolbox CircStat mà paper dùng. Cách tính tròn này chính là thứ paper dùng để tránh lỗi "trung bình của 23:59 và 00:01 là 12:00", nên **không cần** bước "Ngày Sinh Học / tâm giấc ngủ" tự đặt ra ở bản cũ (đã loại).
  4. Theo đúng dấu của paper (*"subtracting the non-class day median phase from the class day median phase"*):
     $$\text{SJL}_{\text{signed}} = \operatorname{wrap}_{(-720, 720]}\big(\tilde{\phi}_{\text{class}} - \tilde{\phi}_{\text{non-class}}\big) \ \text{(phút)}, \qquad \text{SJL} = \lvert \text{SJL}_{\text{signed}} \rvert$$
     $\text{SJL}_{\text{signed}} < 0$ $\Rightarrow$ **sớm pha (`PHASE_ADVANCE`) vào ngày có lớp** — hướng mà paper thấy tương quan âm với GPA mạnh nhất; $> 0$ $\Rightarrow$ `PHASE_DELAY`. *(Bản cũ lấy non-class − class rồi gán nhãn ngược nên báo `PHASE_DELAY` cho trường hợp lớp sáng kéo pha sớm lên — đã sửa.)*
  5. Cảnh báo khi $\text{SJL} > 30$ phút (mốc thực nghiệm: 60% sinh viên vượt mức này).
  6. **Chẩn đoán phụ — Cross-Day Phase Dispersion:** độ lệch chuẩn **tròn** $\sqrt{-2\ln \bar{R}}$ (đổi ra phút) của trung vị pha từng ngày. Chỉ báo cáo, **không** đưa vào phán quyết, vì *internal desynchrony* chỉ là giả thuyết trong phần Discussion của paper.
  - *Đã loại* **Pre-Bedtime Heavy Load Count (`≤ 60 phút` trước giờ ngủ)**: ngưỡng 60 phút không có trong paper nào; Kroese (trích qua Svartdal) chỉ nói về việc đi ngủ muộn hơn dự định, mà `SLEEP` đã là ràng buộc cứng `H2`.

---

#### TRỤ CỘT P3 — Sustainable Pacing & Focus Continuity *(Nhịp độ bền vững cả tuần)*

##### `P3.1` — Weekly Load Spreading & Utilization Adequacy
*(Schaerf — Colorni 1992 tr. 8, Papoulias tr. 10; Gombolay §2.5.4 & Ch. 6 tr. 143, 181)*
- **Công thức:**
  1. Gọi $L_d$ là tổng phút `BLOCK` đặt trong ngày $d$ và $F_d$ là tổng phút rảnh sau `SLEEP` + `OCCUPIED` của ngày $d$ trên **các ngày hoạt động $D_{\text{active}}$ từ `now_slot` tới hết cửa sổ làm việc thực tế** ($\max_t d_t$ nếu chỉ có task `DEADLINE`, hoặc hết `horizon_days` nếu có task `HABIT`/không hạn — tránh phạt oan những ngày cuối tuần nằm sau toàn bộ hạn chót):
     $$\text{DailyLoadStd} = \text{std}(L_d)_{d \in D_{\text{active}}}, \qquad \text{DailyUtilStd} = \text{std}\!\left(\frac{L_d}{\max(15, F_d)}\right)_{d \in D_{\text{active}}}$$
  2. **Awake Utilization Ratio:** $\text{Util} = \frac{\text{BLOCK} + \text{OCCUPIED}}{\text{Tổng slot thức trong [now\_slot, horizon\_slots)}}$ và đối chiếu song song với điểm khớp sở thích (`P2.1`). Theo **Gombolay (tr. 181)**, phải tránh cả **nhàn rỗi bất thường** (bỏ trống khi còn việc chưa xếp) lẫn **tỷ lệ lấp lịch cực đoan** làm suy sụp khả năng giữ bức tranh tổng thể của người học.

##### `P3.2` — Clustering, Meal-Boundary & Context-Switching Cost
*(Schaerf §4.2 tr. 25 — Corne et al. 1993, Carter et al. 1994, Laporte & Desroches 1984; Vieira tr. 47 — setup giữa các lớp công việc)*
- **Công thức (đều dùng đơn vị đếm nguyên tự nhiên, dễ kiểm tra từng ngày):** Corne phạt 3 lỗi *"in descending order of weight"* nhưng Schaerf **không cho trọng số số học** $\Rightarrow$ không cộng thành điểm (bản cũ dùng `10:3:1` là tự bịa), mà giữ **vector** $[\text{(1)}, \text{(2)}, \text{(3)}]$ và so sánh **từ điển**:
  1. **Heavy-Day Overload (`Corne` (i)):** Số ngày có **`> 2` phiên `cognitive_load == 3`** trong cùng 1 ngày — mức nặng nhất.
  2. **Consecutive Heavy Pairs (`Corne` (ii), `Carter`):** Số cặp phiên `load == 3` cùng ngày nối liền nhau, cách nhau $\le 1$ slot (*"consecutive periods"*; `≤ 1 slot` là cách Project ánh xạ "kỳ liền kề" vào lưới 15 phút, vì 1 slot `REST` là khoảng nghỉ tối thiểu của SmartSchedule). Bỏ điều kiện "cùng một buổi" của bản cũ (paper không có).
  3. **Meal-Boundary Offenses (`Corne` (iii), `Carter` coi hai đầu bữa trưa là liên tiếp):** Số lần có block học kết thúc **đúng lúc bắt đầu** VÀ block học bắt đầu **đúng lúc kết thúc** một `FixedEvent` loại `MEAL`.
  4. **Context-Switching Count (`Vieira tr. 47` — setup khi tài nguyên chuyển giữa các lớp công việc, Mehta & Uzsoy; báo riêng, không thuộc vector Corne):** Số cặp block liên tiếp trong ngày (khoảng cách $0 \le \text{gap} \le 2$ slot = `30 phút`) nhưng **khác `category`** (`context_switches`), đối chiếu với `batched_pairs` (cùng loại để giữ mạch tập trung).

---

#### TRỤ CỘT P4 — Execution Robustness & Plan Stability *(Năng suất thực sống sót qua sai số & đổi ít khi có biến cố)*

##### `P4.1` — Protective Buffer Adequacy & Shock-Tested Effective Completion Rate
*(Vieira — Mehta & Uzsoy tr. 53, 56; Daniels & Kouvelis tr. 45, 53; O'Donovan tr. 53; Myers EMP tr. 6–7)*
Đây là tiêu chí then chốt nối từ "bản vẽ tĩnh" sang **"năng suất thực ngoài đời"**:
1. **True Buffer Ratio (`Mehta & Uzsoy`, `EMP`):** Tỷ lệ tác vụ có đệm phòng vệ thực sự (không đếm nhầm phần làm tròn lên 15 phút):
   $$\text{HasBuffer}(t) \iff \text{get\_planned\_duration\_min}(t) > \text{round\_up\_to\_15}(t.\text{duration\_min})$$
   Kèm **Zero-Slack Risk Blocks**: số block không có ít nhất 1 slot trống ngay sau đuôi trước `OCCUPIED` (`FixedEvent`) / `SLEEP` / block khác / `deadline_slot`.
2. **Shock-Tested Effective Completion Rate (`Daniels & Kouvelis` + tham số cấu hình của Project `+25%` và `+50%`):**
   - **Điểm chốt kỹ thuật tránh tính sai Buffer:** Phải áp mức sốc $+s \in \{+25\%, +50\%\}$ lên **thời lượng ước lượng thô `raw Task.duration_min`** (chia tỷ lệ tương ứng cho từng chunk: $\text{raw\_chunk\_min}_c = \text{raw\_duration\_min} \times \frac{\text{block}_c.\text{duration\_min}}{\text{planned\_duration\_min}}$), **tuyệt đối không nhân `+s` đè lên `block.duration_min` vốn đã cộng sẵn buffer**! Khi đó, độ tràn vượt ngoài đuôi block là:
     $$\text{shocked\_slots}_c = \left\lceil \frac{\text{raw\_chunk\_min}_c \times (1 + s)}{15} \right\rceil, \qquad \text{spill\_slots}_c = \max\big(0,\; \text{shocked\_slots}_c - \text{block\_slots}_c\big)$$
     - Nếu `buffer_multiplier` đã đủ lớn (ví dụ $\alpha = 1.35$ đối với sốc $+25\%$), phần đệm bên trong block **tự hấp thụ hết cú sốc (`spill = 0`)**!
     - Nếu có $\text{spill\_slots}_c > 0$, mô phỏng phần tràn nối tiếp từ `block.end_slot` xem nó có lọt an toàn vào khe đệm `FREE`/`REST` phía sau không, hay đâm vào `SLEEP` / `OCCUPIED` / `deadline_slot` / đẩy dây chuyền chạm block kế tiếp.
   - Block `DONE` đã thực thi xong nên **không** bị áp sốc (chỉ giữ làm mốc kết thúc).
   - Tính **Shock-Survived Priority Rate ($\%$):** tổng `priority` của các task `DEADLINE` mà mọi chunk hoàn tất **an toàn trước hạn dưới mức sốc $+25\%$ / $+50\%$** chia cho tổng `priority` ban đầu. Đây là phép thử **trường hợp xấu** (Daniels & Kouvelis — tối ưu worst-case khi không có phân phối xác suất), nên tràn vào `SLEEP`/`OCCUPIED` được tính là thất bại. Bất biến kiểm tra chính bộ mô phỏng: $\text{P1.1} \ge \text{Shock@+25\%} \ge \text{Shock@+50\%}$.
   - *Giá trị thực tiễn:* Nếu Lịch X xếp khít 0 phút đệm (`P1.1 = 100%` trên giấy), dưới sốc `+25%` chỉ còn `40%` sống sót; còn Lịch Y dùng `COGNITIVE_LOAD` buffer (`P1.1 = 100%`, `Shock@25% = 95%`) $\rightarrow$ **Lịch Y chắc chắn tạo ra năng suất thực cao hơn Lịch X**.
3. **Realized vs. Planned Deviation (`O'Donovan`):** Khi đầu vào hoặc CSDL có `completion_logs` (`actual_duration_min`, `estimated_duration_min`), tính sai lệch tuyệt đối trung bình $\lvert \text{actual\_duration\_min} - \text{planned\_duration\_min} \rvert$ và tỷ số hiệu chuẩn `actual_duration_min / estimated_duration_min` để phát hiện lịch đặt buffer quá non hay quá dư.

##### `P4.2` — Post-Repair Plan Stability & Near-Term Preservation *(Chỉ kích hoạt khi đánh giá Rescheduling / Overrun)*
*(Fox et al. 2006 §2, §3 Def. 2–3, §5.2 tr. 2–3, 9; Vieira tr. 46–50; Myers tr. 8, 13)*
So sánh **phần kế hoạch chưa thực thi** (các block có `end_slot > now_slot` — theo đúng `Fox §2 tr. 2`) giữa lịch gốc $\pi_0$ và lịch sau sửa $\pi_1$, chuẩn hóa mỗi hành động thành tuple $a = (\text{task\_id}, \text{chunk\_index}, \text{start\_slot}, \text{end\_slot})$:
1. **Symmetric Plan Difference (`Fox Def. 2`):**
   $$D(\pi_0, \pi_1) = \lvert \pi_1 \setminus \pi_0 \rvert + \lvert \pi_0 \setminus \pi_1 \rvert$$
   *(Bất kỳ block nào bị dịch giờ, xóa, thêm mới hoặc giãn độ dài do overrun đều tăng $D$; hoàn toàn bất biến theo đúng định nghĩa lý thuyết của Fox et al.)*
2. **Near-Term & First-Step Preservation (`Fox §5.2`, tr. 9):**
   Fox đo `Orig`/`Diff` trên **"initial actions"** của kế hoạch (các hành động ở bước đầu, thường song song nhiều hành động). Với lịch một người, Project ánh xạ "initial actions" = các block chưa thực thi **bắt đầu trong `near_term_window_slots` (mặc định `96` slot = `24h`) sau `now_slot`** — đây là **tham số Project**, không phải số của paper. Cửa sổ rỗng $\Rightarrow$ `Orig`/`Diff` = `N/A` (bỏ cơ chế "lấy tạm 5 block đầu" tự chế của bản cũ):
   - **`Eq 1st` (`Bool`):** Block hành động đầu tiên ngay sau `now_slot` của $\pi_0$ và $\pi_1$ có giữ nguyên hoàn toàn không? (Quan trọng khi sinh viên cần bắt tay vào làm ngay mà không bị đổi kế hoạch phút chót.)
   - **`Orig%` (cao hơn là tốt):** `%` block cận kề trong $\pi_1$ xuất hiện nguyên vẹn trong $\pi_0$.
   - **`Diff%` (thấp hơn là tốt):** `%` block cận kề trong $\pi_0$ đã bị mất khỏi $\pi_1$.
3. **Timing & Ordering Metrics (`Vieira` + `Myers`):**
   - **Mean Absolute Time Shift $\Delta t$** (`Cowling & Johansson 2002`, tr. 46 — *"average absolute change of the start and completion times"*): trung bình của **cả** $\lvert \text{start}_1 - \text{start}_0 \rvert$ **và** $\lvert \text{end}_1 - \text{end}_0 \rvert$ trên các block khớp `(task_id, chunk_index)` (bản cũ chỉ lấy start nên bỏ sót block bị giãn độ dài do overrun).
   - **Sequence Inversion Count** (`Wu et al. 1993`, tr. 47): số cặp block bị đảo thứ tự trước–sau.
   - **Moved / Unplaced Count** (`Bean et al. 1991`, tr. 48), `calculate_schedule_stability`, đánh giá khả năng hấp thụ bằng slack (`Wu & Li 1995`, tr. 50), và nhãn `Rescheduling Effort (LOW / MEDIUM / HIGH)` (`Myers Towel UI tr. 13`).

---

### 3.3. Tầng 2 — Giải Thích (`D1`), Đối Chiếu Thuật Toán (`D2`) & Nhánh Người Dùng (`D3`)

- **`D1` — ICEE Root-Cause Critiques & Non-Noise Budget (`Myers ICEE tr. 9–10`; `Yoshikawa COASTOOL`; `Gombolay tr. 137 & §7.2.1 tr. 189`):**
  - Không xả hàng chục dòng cảnh báo nhỏ nhặt gây tê liệt người dùng (Gombolay tr. 137: điều dưỡng bị *"deluge of false alarms and non-critical alerts"* nên thờ ơ với thông tin trên màn hình). Giới hạn báo cáo tối đa **Top `max_icee_critiques` (mặc định 5 — tham số Project)** nguyên nhân tác động lớn nhất làm giảm điểm P1–P4.
  - Mỗi mục gồm 4 phần chuẩn `ICEE`: **(1) Mã trụ cột**, **(2) Định danh chính xác `task_id` / `block_id` / `day`**, **(3) Lý do so sánh** (vì sao đặt thế này làm tụt năng suất so với lựa chọn khác — `Gombolay §7.2.1`), và **(4) Hành động khắc phục gợi ý** (`Myers Towel UI`).
- **`D2` — Relative Cross-Solver Comparison (`Schaerf §5.1, §7.3–7.5`; `Gombolay §5.3`) & Chỉ Số Chẩn Đoán Phụ:**
  - Tuyệt đối không nén thành 1 con số điểm tổng mờ kiểu $0.3 x + 0.7 y$. Luôn xuất **Vector Giá Trị Gốc Tự Nhiên** và so sánh các solver (`EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`) trên **cùng `seed` input** bằng **Thứ tự Từ Điển (`Lexicographic Verdict`)**:
    1. **Cấp 1 (`G1` + `P1.1`):** Hợp lệ cứng ($C_{\text{hard}}=0$, giữ `PINNED`) và hoàn thành tối đa giá trị `priority` đúng hạn (`DEADLINE`).
    2. **Cấp 2 (`P4.1`):** Sức sống của lịch qua biến động (`Shock-Survived Priority Rate @+25%`).
    3. **Cấp 3 (`P2` + `P1.2`):** Chất lượng não bộ — `HeavyPeakPct`, tuân thủ nghỉ `>10p`, tránh ép *phase advance*, tránh dồn `<10h` bất hợp lý & ổn định SJL.
    4. **Cấp 4 (`P3`):** Vector Corne $[>2 \text{ nặng/ngày}, \text{cặp nặng liền kề}, \text{kẹp bữa}]$ so sánh từ điển, rồi tới độ lệch tải theo ngày.
  - Kèm bảng **Diagnostic phụ** (chỉ để kỹ thuật viên soi): `fragmentation_index` tính trên `horizon_slots` thực tế, `execution_time_ms` (`Vieira tr. 48`), `work_rhythm` compliance, và `PersonalHabit` fulfillment.
- **`D3` — Longitudinal Human-in-the-Loop Evaluation *(Tách khỏi Auto-Evaluator)*:**
  - Dành riêng cho giai đoạn thử nghiệm với người học thật: ghi nhận tỷ lệ chấp nhận gợi ý tốt / bác bỏ gợi ý kém (`Type I / Type II`, `Gombolay Ch. 5 tr. 128, 134–136`), mức hiểu bối cảnh (`SAGAT`, `Ch. 6`), `Berry PTIME 60% benchmark` (Gombolay trích Berry et al.: tỷ lệ chấp nhận gợi ý của PTIME chỉ `60%`), người dùng ít chịu được gợi ý kém (`Myers tr. 9`), và điểm hài lòng `1–5 ⭐` (thang Project tự đặt). Không trộn vào bộ test tự động.

### 3.4. Bảng Minh Họa: Vì Sao Hệ Thống Mới Phân Biệt Đúng Lịch "Tốt Thật" vs "Tốt Giả"?

Xét cùng **1 sinh viên `Owl` (`EVENING` Peak 18:00–24:00)**, có 4 môn/đồ án (`priority = 5, 5, 4, 3`, `load = 3`) và 3 việc nhẹ (`priority = 1`, `load = 1`), tổng tải $\rho = 0.65$ (dư thời gian):

| Chỉ số | Lịch Giả Tốt *(Kiểu EDF nhồi sớm)* | Lịch Năng Suất Cao *(Chuẩn 4 Trụ Cột)* | Kết luận phản ánh đúng Productivity |
|---|---|---|---|
| **G1 (`C_hard`, `PINNED`)** | `0` vi phạm, giữ `PINNED` | `0` vi phạm, giữ `PINNED` | Cả hai đều **Hợp lệ cứng** |
| **P1.1 (`ValueRate` tĩnh)** | `100%` (`20/20` điểm priority) | `100%` (`20/20` điểm priority) | Nhìn kiểu cũ (`% scheduled`) hai lịch **bằng nhau!** |
| **P2.1 (`HeavyPeak` / Ép sáng)** | `18%` Peak, **3 lần ép Owl học `load=3` lúc 07:00 sáng** | **`88%` Peak (tối 19:00–22:00)**, `0` lần ép sáng | Lịch 1 ép học giờ não buồn ngủ $\rightarrow$ năng suất thực giảm mạnh |
| **P2.2 (`Nghỉ >10p` sau nặng)** | `50%` (2 phiên nặng dính liền không nghỉ) | **`100%`** (có nghỉ 15p sau mọi phiên nặng) | Lịch 1 tích tụ mệt mỏi nhận thức (`Albulescu`) |
| **P3.2 (`>2 nặng/ngày`)** | **2 ngày có 3–4 phiên nặng** (cố dồn cho xong Thứ Hai–Thứ Ba) | **`0` ngày vượt ngưỡng**, tải rải đều Thứ Hai–Thứ Bảy | Lịch 1 đốt sức đầu tuần, dễ gãy nhịp |
| **P4.1 (`Buffer` & `Shock@+25%`)** | `0%` buffer; **`Shock@+25%` chỉ sống `55%` priority** | `100%` buffer; **`Shock@+25%` sống `95%` priority** | Khi có phát sinh nhẹ, Lịch 1 vỡ dây chuyền ngay! |
| **Phán quyết của Bộ Đánh Giá** | **`FEASIBLE_BUT_LOW_PRODUCTIVITY`** | **`HIGH_PRODUCTIVITY`** | Bắt trúng bệnh **"xếp kín lịch nhưng không hiệu quả"**! |

---

## 4. Thiết Kế Chi Tiết Hệ Thống Test 2 Phần: `Gen Input` $\rightarrow$ `Run Project` $\rightarrow$ `Evaluate Output`

Toàn bộ pipeline kiểm thử kế thừa phương pháp sinh bài toán có kiểm soát nút thắt của **Gombolay (§3.4.1 & §5.3)** và biến thiên nhiễu có hệ thống của **Fox et al. (§5.1)**:

```text
╔══════════════════════════════════════╗     ╔══════════════════════════╗     ╔══════════════════════════════════════════╗
║ PHẦN 1: BỘ SINH INPUT                ║     ║ CHẠY PROJECT THỰC TẾ     ║     ║ PHẦN 2: BỘ ĐÁNH GIÁ OUTPUT               ║
║ (InputGenerator)                     ║     ║ (Domain Controller / API)║     ║ (OutputEvaluator)                        ║
╠══════════════════════════════════════╣     ╠══════════════════════════╣     ╠══════════════════════════════════════════╣
║ 1. Chọn Regime (1..6) & Seed cố định ║     ║ • Chạy đủ 5 Solver:      ║     ║ 1. Chấm G1-G2 (Cổng khả thi & tải ρ)     ║
║ 2. Sinh CommitmentsProfile:          ║────►║   EDF, LST, WSPT,        ║────►║ 2. Chấm P1-P4 (4 Trụ cột Productivity)   ║
║    - Chronotype (Lark/Finch/Owl)     ║JSON ║   SCORED_GREEDY,         ║ Out ║ 3. Chạy thử Sốc +25%/+50% lên Output     ║
║    - Lịch lớp lệch ngày + 3 Bữa ăn   ║Input║   BACKTRACK              ║ put ║ 4. Xuất Phán Quyết Từ Điển + Top D1 ICEE ║
║    - SleepSchedule & Horizon (7/14d) ║     ║ • (Regime 6) Chạy tiếp:  ║     ║ 5. Kiểm chứng Invariants Regime (PASS/   ║
║ 3. Sinh Tasks (DAG + start_after +   ║     ║   LOCAL_INSERTION,       ║     ║    FAIL) & So sánh chéo đa solver (D2)   ║
║    load/rhythm/buffer) + Habits/Pins ║     ║   RIPPLE_SHIFT,          ║     ╚═════════════════════╤════════════════════╝
║ 4. Validate khả thi TRÊN LƯỚI        ║     ║   FULL_REBUILD & Overrun ║                       ▼
║    bằng planned_duration_min         ║     ╚══════════════════════════╝      [Báo cáo JSON + Bảng chẩn đoán Tiếng Việt]
╚══════════════════════════════════════╝
```

---

### 4.1. Phần 1 — Bộ Sinh Input Phù Hợp Cho Project (`InputGenerator`)

#### Bước thực thi chuẩn khi sinh 1 Test Case (`generate_case(regime, seed)`)
1. **Khởi tạo bộ sinh ngẫu nhiên xác định (`RNG(seed)`):** Bảo đảm bất kỳ test case lỗi nào đều tái lập lại y hệt `100%` theo cặp `(regime, seed)`.
2. **Sinh Hồ sơ Sinh viên (`CommitmentsProfile`):**
   - Chọn Chronotype gắn vào `focus_preference` / `CircadianEnergyProfile`: `MORNING` (*Lark*), `BALANCED` (*Finch*), hoặc `EVENING` (*Owl*) *(kèm biến thể `AFTERNOON` nếu cần)*.
   - Sinh `SleepSchedule` (6.5h–8h/đêm, mặc định `23:00–07:00`, `is_hard_lock=True`).
   - Sinh `FixedEvent` bảo đảm **không tự chồng chéo giờ nhau**:
     - `MEAL`: đủ 3 bữa Sáng/Trưa/Tối mỗi ngày (ví dụ `07:15–07:45`, `12:00–12:45`, `18:30–19:15`) để kiểm chứng **P3.2 Meal-Boundary**.
     - `ACADEMIC_CLASS`: hỗ trợ 2 chế độ — **Lịch lệch ngày kiểu đại học** (học sáng T2/T4/T6, trống T3/T5/cuối tuần để sinh và đo **P2.3 Social Jetlag**) và **Lịch đều các ngày** (để cô lập tác động *phase advance* của **P2.1**).
   - Chọn `horizon_days` (`7` hoặc `14` ngày), `buffer_mode` (`COGNITIVE_LOAD` với `alpha_light=1.20, alpha_heavy=1.35`, hoặc `HABIT`), và tùy chọn `PersonalHabit` (tần suất/tuần, `preferred_window`).
3. **Sinh Tập Công Việc (`List[Task]`) & Ghim (`pinned_blocks`):**
   - Sinh thuộc tính đa dạng để **tạo sự phân biệt thực sự giữa các thuật toán** (nếu không các solver sẽ cho lịch giống hệt nhau!): trộn lẫn `priority` (`1..5`), `cognitive_load` (`1, 2, 3`), `category` (`EXAM`, `PROJECT`, `ASSIGNMENT`, `DEADLINE`, `HABIT`), `work_rhythm` (`LIGHT`/`BALANCED`/`FLOW`), `preferred_window`, `is_splittable` (`True`/`False`), `depends_on`, và `start_after`.
   - Khóa đồ thị phụ thuộc **100% là DAG một chiều** ($j < i$, không tạo chu trình trừ khi chạy test lỗi riêng).
4. **Kiểm tra Khả Thi Đầu Vào Trên Lưới Thật *(bắt buộc cho `Regime 1–4`)*:**
   - Dựng lưới `TimeGridManager` từ profile vừa sinh để đếm chính xác slot `FREE` thực tế theo từng khoảng trước deadline (đã trừ `SLEEP`, `MEAL`, `ACADEMIC_CLASS` và `pinned_blocks`).
   - Chạy qua **`expand_personal_habits` $\rightarrow$ `apply_estimate_buffer`** rồi mới kiểm tra khả thi bằng **`planned_duration_min`** (sau buffer), không kiểm tra bằng `duration_min` thô:
     - `start_after_slot + planned_slots <= deadline_slot`
     - `deadline_slot(parent) + child_planned_slots <= deadline_slot(child)`
     - Cộng dồn nhu cầu slot từ `now_slot` tới từng mốc deadline `d` luôn nhỏ hơn hoặc bằng tổng slot `FREE` liên tiếp khả dụng cho từng chunk không tách mảnh.
   - Đạt mọi kiểm tra + vượt qua schema validation của `CommitmentsProfile` & `Task` mới xuất ra.
5. **Gắn Metadata cho Báo cáo:** Lưu kèm `(seed, regime, chronotype, horizon_days, planned_demand_slots, usable_free_slots, tightness_rho)`.

#### Đặc tả 6 Regimes Kiểm Thử Có Kiểm Soát
*(Các dải $\rho$ là tham số độ khó cấu hình của Bộ Sinh Input, không phải ngưỡng lý thuyết bài báo.)*

| Regime | Tên Kịch Bản | Cấu Hình Đầu Vào Đặc Trưng | Mục Tiêu Đo & Bất Biến (`Invariants`) Phải Đúng |
|---|---|---|---|
| **Regime 1** | **`LOOSE_FEASIBLE`** *(Tải nhẹ $\rho \approx 0.35\text{--}0.55$)* | Nhiều slot rảnh, pha trộn `priority 1..5`, `load 1..3`, có `preferred_window` và `category` khác nhau | Mọi solver đều đạt `P1.1 = 100%`; dùng để **bóc trần bẫy `% scheduled`** (`Schaerf §5.1`): `SCORED_GREEDY` / `BACKTRACK` bắt buộc phải vượt `EDF` về **P2.1** (khớp Peak & window) |
| **Regime 2** | **`TIGHT_DEADLINE_CLUSTER`** *(Tải sát ngưỡng $\rho \approx 0.80\text{--}0.95$)* | Nhiều `DEADLINE` dồn cùng 2–3 ngày cuối, xen kẽ `priority=5` với `priority=1`, nhiều chunk dài cạnh `MEAL` | Thử thách giữ **`P1.1` Priority Value**, đo `SlackMargin`, soi lỗi **`P3.2`** (`>2` phiên nặng/ngày, kẹp 2 đầu bữa ăn, context switch) và kiểm tra sức chịu đựng **`P4.1 Shock@+25%`** |
| **Regime 3** | **`CIRCADIAN_SJL_AND_RECOVERY`** | Profile `EVENING` (*Owl*) hoặc `MORNING` (*Lark*), lịch học `ACADEMIC_CLASS` lệch ngày (T2/T4/T6 sáng), nhiều task `load=3` (kèm nhánh đủ chặt để kích hoạt `Crunch Tier 1`) | Thử nghiệm **P2.1** (tránh ép *Owl* học `load=3` vào khung sáng `06:00–12:00` khi chiều/tối còn trống), **P2.2** (đảm bảo nghỉ `>10p` sau task nặng trừ khi bị `Crunch Tier 1`), và đo **P2.3 Circular SJL** (`>30p` & ổn định pha) |
| **Regime 4** | **`PROCRASTINATION_ONSET_AND_DAG`** | Chuỗi `depends_on` 2–3 bậc, task `load=3` có `start_after` mở sớm & cửa sổ tới deadline rất rộng (`> 24h`), kèm nhánh cần *strategic idling* (đợi slot chuẩn cho task gấp khác) | Kiểm định **P1.2**: phát hiện đúng ca trì hoãn dồn `<10h` bất hợp lý vs **không phạt nhầm** chờ hợp lệ do `depends_on`, `start_after`, *strategic idling* (`Gombolay`) hay đợi Peak trong ngày |
| **Regime 5** | **`OVERLOAD_INFEASIBLE`** *(Quá tải $\rho \in [1.15, 1.50]$)* | Tổng `planned_slots` cố ý vượt quá `usable_free_slots`; chứa cả `priority=5` lẫn `priority=1..2` và `PersonalHabit` | Kiểm định **G2** (nhận diện đúng $\rho > 1$ là quá tải cấu trúc), đo **`P1.1` Distance to Feasibility** và xác nhận thuật toán bảo toàn nhóm `priority` cao tốt hơn nhóm ưu tiên thấp |
| **Regime 6** | **`DISRUPTION_AND_OVERRUN_SERIES`** *(Nhóm biến cố tăng dần kiểu Fox §5.1)* | Từ lịch nền tốt + `pinned_blocks`, bơm chuỗi nhiễu từ nhẹ $\rightarrow$ nặng: (a) 1 sự cố `DisruptionEvent` 2h, (b) 1 task bị `overrun` thực tế $+50\%$, (c) nhiều sự cố chồng lên chuỗi `depends_on` | Sinh cặp `(baseline π₀, repaired π₁)` và kiểm định **P4.2**: `LOCAL_INSERTION` phải có $D(\pi_0, \pi_1)$ nhỏ hơn, `Eq 1st` & `Orig%` cao hơn, `Diff%`, $\Delta t$ & đảo thứ tự thấp hơn `FULL_REBUILD`, đồng thời giữ nguyên `100%` block `PINNED` hợp lệ (`G1`) |

---

### 4.2. Bước Chạy Project (`Run Project`)

Pipeline hỗ trợ cả 2 chế độ thực thi để chắc chắn đánh giá khớp với hành vi thật của ứng dụng:
1. **Direct Controller Execution *(tốc độ cao cho chạy hàng loạt multi-seed)*:**
   - Gọi hàm điều phối trung tâm của ứng dụng (`solve_schedule`) lần lượt qua cả **5 solver**: `EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`.
   - Ở `Regime 6`: gọi tiếp bộ sửa lịch qua cả 3 chế độ **`LOCAL_INSERTION`**, **`RIPPLE_SHIFT`**, **`FULL_REBUILD`** (`repair_disruption` / `compare_repair_modes`) và luồng xử lý tràn giờ **`handle_task_overrun`** *(chú ý truyền tập task đã qua `expand_personal_habits` và `apply_estimate_buffer` khi đối chiếu `P4.2` để không lệch số lượng task với lịch gốc)*.
2. **HTTP API End-to-End Execution *(xác thực đúng định dạng giao tiếp Web)*:**
   - Gửi JSON payload từ Phần 1 tới endpoint lập lịch chính, sau đó ở `Regime 6` gọi tiếp các endpoint sửa lịch (`repair`), cập nhật tiến độ khi quá giờ (`progress` & `overrun`), và ghi nhận hoàn thành công việc (`complete`) để lấy output JSON y hệt giao diện web nhận được.

---

### 4.3. Phần 2 — Bộ Đánh Giá Output (`OutputEvaluator`)

#### Quy trình xử lý 5 bước của `OutputEvaluator`
1. **Bước 1 — Chuẩn hóa đầu vào-đầu ra:** Chạy đúng chuỗi `expand_personal_habits(profile, tasks)` $\rightarrow$ `apply_estimate_buffer(profile, ...)` trước khi gọi `get_planned_duration_min()`, và dựng lại bản sao `TimeGridManager` trên đúng `horizon_slots` thực tế (không làm biến đổi dữ liệu gốc).
2. **Bước 2 — Chạy Cổng `G1–G2`:** Xác nhận $C_{\text{hard}}=0$ (gồm đủ 5 kiểm tra bổ sung + bảo toàn `PINNED`) và tính $\rho$.
3. **Bước 3 — Tính trọn 4 Trụ cột `P1–P4` + Mô phỏng Sốc `+25% / +50%` trên `raw duration_min`:** Xuất **Vector Giá Trị Gốc Tự Nhiên** (không gộp tổng mờ) kèm tỷ lệ sống sót sau sốc và các chỉ số `P4.2` nếu có `baseline_schedule`.
4. **Bước 4 — Suy diễn Phán Quyết Từ Điển (`Lexicographic Verdict`) & Top 3–5 Cảnh Báo `ICEE` (`D1`):**
   - **`INVALID`:** Khi `G1 > 0` (có vi phạm cứng hoặc mất `PINNED`).
   - **`OVERLOAD_TRIAGE`:** Khi `G1 == 0`, có task rơi (`P1.1 < 100%`) và `G2` xác nhận $\rho > 1.0$ $\rightarrow$ đánh giá chất lượng triết lý giữ `priority` cao & cảnh báo cắt giảm.
   - **`SUBOPTIMAL_ALGORITHM_FAILURE`:** Khi `G1 == 0`, $\rho \le 1.0$ nhưng vẫn để rơi task có hạn (`P1.1 < 100%`).
   - **`FEASIBLE_BUT_LOW_PRODUCTIVITY` (`Gombolay §5.3`):** Khi `G1 == 0` và `P1.1 == 100%`, **nhưng vi phạm $\ge 1$ lỗi nghiêm trọng cấp Trụ cột hoặc $\ge 2$ cảnh báo mức vừa** theo bộ tham số chính sách cấu hình được (`EvaluationConfig`, mặc định cảnh báo khi: ép *phase advance* `Owl` vào `06:00–12:00` dù còn slot Peak chiều/tối; mất nghỉ `>10p` sau việc `load=3` khi không bật `Crunch Tier 1` (có `Crunch Tier 1` $\rightarrow$ chỉ là cảnh báo vừa); có ngày `>2` phiên nặng; dồn `<10h` vô lý trên cửa sổ rộng; `Shock@+25%` làm tụt mạnh tỷ lệ giá trị sống sót; hoặc `SJL > 30 phút`). Các ngưỡng % trong `EvaluationConfig` là **chính sách Project**, không phải số của paper.
   - **`HIGH_PRODUCTIVITY`:** `G1 == 0`, tối đa hóa `P1.1` theo khả năng tải $\rho$, các trụ cột `P2–P4` không dính lỗi nghiêm trọng.
5. **Bước 5 — Đối chiếu đa thuật toán (`D2`) & Kiểm định `Invariants` theo Regime (`PASS / FAIL`)**.

#### Bộ Tự Kiểm Định Độc Lập Của Chính Bộ Đánh Giá (`Contrast Pairs`, `Gombolay §5.3 tr. 131`)
Trước khi tin dùng `OutputEvaluator` để chấm solver thật, chạy một bộ kiểm thử cố định gồm **3 lịch nhân tạo trên cùng 1 input**:
1. **Lịch Chuẩn (`Golden High-Productivity`):** `G1=0`, `load=3` vào Peak, nghỉ 15p sau mỗi việc nặng, buffer đầy đủ, rải tải đều.
2. **Lịch Bẫy (`Feasible-But-Low-Productivity`):** Cố ý giữ `G1 = 0` và `P1.1 = 100%`, **nhưng** nhét `3` phiên nặng vào 1 buổi sáng `07:00` của sinh viên `EVENING`, cắt sạch nghỉ 15p, dồn `load=3` sang đoạn `<10h` trước hạn, `0%` buffer.
3. **Lịch Lỗi (`Infeasible`):** Cho 1 block vượt deadline hoặc đè `SLEEP` / lệch `start_after`.
- **Điều kiện PASS của `OutputEvaluator`:** Phải xuất kết quả phân loại chính xác 3 hạng (`HIGH_PRODUCTIVITY` > `FEASIBLE_BUT_LOW_PRODUCTIVITY` > `INVALID`), điểm trụ cột `P2, P3, P4` của Lịch Chuẩn vượt trội Lịch Bẫy, và danh sách `D1 ICEE Critiques` trỏ đúng `task_id` / `block_id` gây lỗi.

#### Bảng Bất Biến `PASS / FAIL` Cho Pipeline 2 Phần
- **Mọi Regime:** Toàn bộ 5 solver không được để `G1 > 0` (`C_hard = 0`, giữ nguyên `PINNED` hợp lệ).
- **`Regime 1`:** Mọi solver đạt `P1.1 = 100%`; `SCORED_GREEDY` / `BACKTRACK` phải vượt `EDF` về **`P2.1 HeavyPeakPct` & `preferred_window`**.
- **`Regime 2`:** *(Đã sửa — bản cũ yêu cầu "solver xét ưu tiên phải giữ `priority=5` ≥ EDF", nhưng không paper nào trong 8 tài liệu khẳng định điều đó khi input **còn đủ sức chứa**; còn code cũ chỉ kiểm tra `max(...) > 0` nên luôn PASS.)* Bất biến mới:
  1. Input được bộ sinh chứng nhận khả thi $\Rightarrow$ `G2` **không** được báo quá tải, và **mọi** solver làm rơi việc có hạn phải bị gán `SUBOPTIMAL_ALGORITHM_FAILURE` (không phải `OVERLOAD_TRIAGE`) — đúng tinh thần Schaerf §5.1 (đánh giá việc rơi theo độ chặt của input). Danh sách solver làm rơi việc được in kèm như **phát hiện về solver**, không phải lỗi của harness.
  2. Bộ mô phỏng sốc phải đơn điệu: $\text{P1.1} \ge \text{Shock@+25\%} \ge \text{Shock@+50\%}$ cho mọi solver.
- **`Regime 3`:** `SCORED_GREEDY` giảm được số ca **ép *phase advance* trên `Owl`** (`P2.1`) so với `EDF`; `OutputEvaluator` tính được `P2.3 Circular SJL` (đúng dấu class − non-class, không gãy qua `00:00`, trả `N/A` khi thiếu loại ngày) và `P2.2` có giá trị.
- **`Regime 4`:** `SCORED_GREEDY` đạt `P1.1 = 100%`, có `Preparatory Margin` và **`0%` dồn `<10h` bất hợp lệ** (không phạt nhầm chờ hợp lệ do `start_after` / `depends_on` / *strategic idling* / đợi Peak). Khả năng **bắt** ca trì hoãn thật được kiểm bằng unit test có lịch cố ý dồn `<10h`.
- **`Regime 5`:** `OutputEvaluator` xếp phán quyết `OVERLOAD_TRIAGE` (không báo oan `SUBOPTIMAL` khi $\rho > 1$) và đo chính xác `Distance to Feasibility` + `Priority Value Retained`.
- **`Regime 6`:** Fox et al. so sánh repair vs replan trên chuỗi biến thể có nhiễu tăng dần, nên kiểm theo từng mức: ở **mọi** mức, `LOCAL_INSERTION` không được kém `FULL_REBUILD` về $D(\pi_0,\pi_1)$, `Eq 1st`, `Orig%`, `Diff%`, $\Delta t$, số đảo thứ tự; ở mức **C (nhiều sự cố chồng nhau)** phải có $D$ **nhỏ hơn hẳn**. Mức A (1 sự cố nhỏ) cho phép hòa vì cả hai cách có thể cho cùng một lịch. Và `0` block `PINNED` hợp lệ bị di chuyển.

#### Cấu trúc Đầu Ra Của Pipeline Test 2 Phần
1. **Báo cáo JSON đầy đủ:** Lưu `seed`, `regime`, `metadata` của Input, Vector `G1–G2` & `P1–P4` của từng solver, kết quả mô phỏng sốc `+25% / +50%`, bảng đối chiếu `D2`, danh sách `D1 ICEE Critiques`, Phán Quyết Từ Điển và kết quả `PASS/FAIL` từng Invariant.
2. **Bảng Tổng Kết Tiếng Việt Dễ Đọc:** Tóm tắt theo 4 khối gọn nhẹ *(Bối cảnh tải $\rho$ & Chronotype $\rightarrow$ Bảng 4 Trụ Cột P1–P4 kèm đơn vị tự nhiên $\rightarrow$ So sánh 5 Solver $\rightarrow$ Top 3–5 Lý do & Gợi ý sửa đổi)*.

---

## 5. Kiến Trúc Tích Hợp Vào Ứng Dụng & Lộ Trình Triển Khai

*(Thiết kế hoàn toàn theo trách nhiệm từng tầng để gắn vào mọi cấu trúc dự án mà không phụ thuộc tên file hay đường dẫn cụ thể.)*

### 5.1. Sáu Bất Biến Kỹ Thuật (`INV-1` .. `INV-6`)
- **`INV-1` (Tách biệt miền nghiệp vụ & harness test):** Lõi chấm điểm `ScheduleEvaluator` chỉ nhận các model/lưới dữ liệu thuần, không gọi tầng HTTP. Toàn bộ `InputGenerator` & `OutputEvaluator` nằm ở tầng kiểm thử độc lập với mã chạy thực tế.
- **`INV-2` (Schema lá độc lập):** Các cấu trúc dữ liệu báo cáo (`EvaluationReport`, `GateContext`, `ProductivityPillars`, `ShockRobustnessResult`, `StabilityReport`, `CritiqueItem`, `EvaluationConfig`) đặt ở tầng schema thuần, không import ngược lại solver hay controller.
- **`INV-3` & `INV-4` (Stateless & Bảo vệ lưới gốc):** Mọi hàm đánh giá và mô phỏng sốc `+25% / +50%` chỉ làm việc trên bản sao cục bộ, tuyệt đối không làm biến đổi `ScheduleOutput` hay mặt nạ `SLEEP` / `OCCUPIED` gốc.
- **`INV-5` (Tối ưu độ trễ cho người dùng Web):** Tách **Chế độ chấm nhanh Inline** (chấm ngay `G1–G2 + P1–P4 + D1` trên 1 output sẵn có + sốc nhẹ `+25%`, không chạy lại 5 solver) khỏi **Chế độ đối sánh sâu (`D2`)** (chỉ chạy khi người dùng bật bảng so sánh thuật toán hoặc chạy trong bộ Test Harness).
- **`INV-6` (Thread-safety):** Không dùng biến trạng thái toàn cục thay đổi được khi chạy đánh giá song song qua nhiều seed.

### 5.2. Điểm Nối Theo Tầng Hệ Thống
- **Tầng Điều Phối & Web API:** Thêm hàm `evaluate_schedule(...)` và endpoint đánh giá (hỗ trợ chấm cả lịch solver lẫn lịch sinh viên tự kéo thả `PINNED`, tùy chọn truyền kèm `baseline_schedule` cho `P4.2` và cờ bật/tắt đối chiếu chéo đa solver). Thay bảng tổng hợp điểm tuyến tính cũ trong chức năng so sánh thuật toán bằng bảng 4 Trụ Cột `P1–P4`.
- **Tầng Giao Diện:**
  - **Student Mode *(Chủ động & Nhẹ nhận thức — `Gombolay Ch. 6`, `Conjecture 1`, `Towel UI`)*:** Hiển thị **4 thẻ trực quan cho 4 Trụ Cột Năng Suất** (*Giá trị kịp hạn — Tỉnh táo sinh học — Nhịp độ bền vững — Độ an toàn trước phát sinh*), **Top 3 gợi ý sửa 1-click** có giải thích lý do (`Gombolay §7.2.1`), giữ chặt quyền ghim `PINNED`, và lưu phản hồi hài lòng `1–5 ⭐` phục vụ nhánh `D3`.
  - **Lab Mode *(Nghiên cứu & Chẩn đoán)*:** Hiển thị trọn Vector giá trị gốc không giấu số (`Schaerf §5.1`), biểu đồ pha tròn 24h SJL ngày có lớp vs ngày trống (`Smarr & Schirmer`), đồ thị sụt giảm tỷ lệ hoàn thành ở mức sốc `0% / +25% / +50%` (`Daniels & Kouvelis`), bảng đối chiếu 5 solver (`D2`) và bảng `D(π₀, π₁)` / `Eq 1st` / `Orig%` / `Diff%` (`Fox et al.`).

### 5.3. Lộ Trình Triển Khai 4 Pha
1. **Pha 1 — Lõi Đánh Giá 4 Trụ Cột & Kiểm Định Tương Phản (`ScheduleEvaluator` + Schema):**
   - Cài đặt trọn **Tầng 0 (`G1–G2`)**, **Tầng 1 (`P1–P4`, gồm Circular SJL theo đúng Smarr & Schirmer & Mô phỏng Sốc `+25% / +50%`)**, và **Bộ Phán Quyết Từ Điển + `D1` Top 3–5 `ICEE`**.
   - Vượt qua `100%` bài kiểm thử **Contrast Pairs (`Good` > `Feasible-Bad` > `Invalid`)**.
2. **Pha 2 — Xây Dựng Hệ Thống Test 2 Phần (`InputGenerator` $\rightarrow$ `Run Project` $\rightarrow$ `OutputEvaluator`):**
   - Hoàn thiện `InputGenerator` sinh đủ **6 Regimes** có kiểm tra khả thi bằng `planned_duration_min` trên lưới thật.
   - Kết nối `Run Project` (cả Direct & HTTP E2E) vào `OutputEvaluator`, xác minh toàn bộ Invariants trên 6 Regimes.
3. **Pha 3 — Thực Nghiệm Đa Seed & Rà Soát Thực Tế:**
   - Chạy ít nhất hàng chục `seed` cho mỗi Regime để đo độ phân biệt giữa `EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`; kiểm tra xem có cảnh báo nào bị spam hoặc thiếu công bằng với trường hợp chờ *strategic idling* hay không để tinh chỉnh logic giải thích.
4. **Pha 4 — Tích Hợp Web API, Giao Diện Student/Lab & Theo Dõi Dài Hạn (`D3`):**
   - Gắn endpoint đánh giá vào Web App (chấm lại được sau mỗi lần kéo-thả lịch tay), dựng 4 thẻ Productivity trên Student Mode, Lab Mode đầy đủ và bộ ghi nhận phản hồi `D3` + kiểm tra toàn bộ `INV-1..INV-6`.
