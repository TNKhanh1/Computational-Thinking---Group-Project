# ⚡ SmartSchedule — Personal Productivity Assistant for Automated Task & Timetable Scheduling

**Môn học:** Tư duy Tính toán (CSC10014) — FIT-HCMUS  
**Nhóm thực hiện:** Group 03 (*The Seven Dwarfs*)

---

## 📂 Cấu Trúc Kho Lưu Trữ (Repository Structure)

1. **[`Proposal/`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Proposal)**
   - [`Proposal_Report.pdf`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Proposal/Proposal_Report.pdf): Báo cáo đề xuất gốc của nhóm (45 trang — Phân rã bài toán, Lưới 672 slots, Ràng buộc cứng/mềm, Kịch bản tuần của Minh).
   - [`Presentation.pdf`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Proposal/Presentation.pdf): Slide thuyết trình đề xuất (53 trang).
2. **[`Baseline_Plan/`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Baseline_Plan)**
   - [`baseline_plan.md`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Baseline_Plan/baseline_plan.md): Bản đặc tả kỹ thuật chi tiết cho hệ thống **Baseline (V0)**.
3. **[`Improve_Plan/`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Improve_Plan)**
   - [`improve_plan.md`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Improve_Plan/improve_plan.md) & [`improve_plan_summary.pdf`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/Improve_Plan/improve_plan_summary.pdf): Bản kế hoạch nâng cấp hệ thống (Giai đoạn 2 — V1/V2).
4. **[`group03-smartschedule-baseline/`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/group03-smartschedule-baseline)** ⭐ **(MÃ NGUỒN ỨNG DỤNG BASELINE V0 HOÀN CHỈNH)**
   - Chứa toàn bộ mã nguồn Backend, Frontend Web Workbench, CLI, 10 kịch bản kiểm thử `T01–T10`, và bộ kiểm thử tự động `pytest`.
   - 👉 **Xem hướng dẫn chi tiết cách chạy, cấu trúc Input, Output và cách đọc kết quả tại:** **[`group03-smartschedule-baseline/README.md`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/group03-smartschedule-baseline/README.md)**.

---

## 🚀 Khởi Chạy Nhanh Bản Baseline (V0)

### 1. Cài đặt thư viện
```powershell
cd group03-smartschedule-baseline
pip install -r requirements.txt
```

### 2. Chạy Giao diện Web (Technical Benchmark Workbench)
Nhấp đúp vào [`group03-smartschedule-baseline/run_app.bat`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/group03-smartschedule-baseline/run_app.bat) hoặc chạy lệnh:
```powershell
cd group03-smartschedule-baseline
python -m uvicorn web.api:app --host 127.0.0.1 --port 8000
```
Mở trình duyệt tại: **`http://127.0.0.1:8000`**

### 3. Chạy Kiểm thử tự động (`pytest`) & Thực nghiệm 10 kịch bản (`T01–T10`)
Nhấp đúp vào [`group03-smartschedule-baseline/run_tests.bat`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/group03-smartschedule-baseline/run_tests.bat) hoặc chạy lệnh:
```powershell
cd group03-smartschedule-baseline
python -m pytest -v
python benchmark_runner.py
python main.py --preset minh --solver EDF --check-determinism
```
