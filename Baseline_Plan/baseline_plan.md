# KẾ HOẠCH NGHIÊN CỨU & TRIỂN KHAI PHIÊN BẢN BASELINE (V0)
## Hệ Thống Xếp Lịch Tự Động SmartSchedule — Personal Productivity Assistant
**Môn học:** CSC10014 — Tư Duy Tính Toán (Computational Thinking - 2026)  
**Đơn vị:** Khoa Công nghệ Thông tin, Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS)  
**Nhóm thực hiện:** Nhóm 03 — The Seven Dwarfs  
**Định dạng tài liệu:** Kế hoạch Kỹ thuật Tổng thể Phiên bản Baseline (Thuật toán, Dữ liệu, Giao diện Web Workbench & Đánh giá Đối chứng)

---

## 1. NGUYÊN TẮC THIẾT KẾ & ĐỊNH HƯỚNG BASELINE

### 1.1. Bản Chất của Baseline trong Nghiên Cứu Khoa Học & Tư Duy Tính Toán
Trong nghiên cứu thuật toán và kỹ thuật hệ thống, **Baseline (Hệ thống mốc chuẩn)** là điều kiện tiên quyết để đánh giá một giải pháp mới. Báo cáo đề xuất (Proposal Report) mới chỉ là bản thiết kế ý tưởng ban đầu; trong quá trình hiện thực hóa hành động (Action Phase), nhóm cần tiếp cận đa chiều, xem xét nhiều giải pháp thuật toán và thiết kế khác nhau để chọn ra giải pháp đối chứng tốt nhất.

**Các yêu cầu nền tảng của phiên bản Baseline:**
1. **Tính độc lập & Tất định (Pure Determinism):** Tuyệt đối không chứa yếu tố ngẫu nhiên (non-deterministic). Cùng một tập dữ liệu đầu vào và các ràng buộc, hệ thống phải luôn cho ra đúng một kết quả duy nhất.
2. **Không AI / Học máy (Zero AI / Zero ML):** 
   - Loại bỏ hoàn toàn mô hình ngôn ngữ lớn (LLM Natural Language Parser - Module M1).
   - Dữ liệu đầu vào hoàn toàn thông qua biểu mẫu cấu trúc rõ ràng trên Web (Structured Forms), các tệp tin cấu trúc chuẩn (`JSON`, `CSV`, `YAML`) hoặc tham số dòng lệnh CLI.
3. **Không Tâm lý học hành vi (Zero Behavioral Psychology):**
   - **Không áp dụng hệ số đệm thời gian (No Planning Fallacy Buffers):** Giữ nguyên thời lượng ước tính thô $T_{\text{planned}} = T_{\text{estimate}}$, không nhân $\times 1.2$ hay $\times 1.35$.
   - **Không phân loại nhận thức (No Cognitive Load):** Công việc không bị phân thành Deep / Medium / Shallow để gán quy tắc thời gian.
   - **Không khớp nhịp sinh học (No Circadian Rhythm Matching):** Không gán mức năng lượng 1–3 cho các khung giờ; mọi giờ trống khả dụng đều có trọng số bình đẳng.
   - **Không tự động chèn khoảng nghỉ (No 15-minute Rest Breaks):** Các công việc có thể xếp liên tiếp nhau nếu đủ thời gian.
   - **Không phạt chuyển ngữ cảnh (No Context-Switching Penalty):** Không áp dụng thuật toán gom cụm (batching) hay tính điểm lân cận (neighbour score).
   - **Không xử lý vùng chết (No Dead-Zone Active Rest):** Các khoảng trống nhỏ (< 30 phút) vẫn được coi là thời gian rảnh hợp lệ (FREE).
4. **Trọng tâm bài toán:** Giải quyết bài toán **Tối ưu hóa Thỏa mãn Ràng buộc Cổ điển (Classical Constraint Satisfaction & Scheduling Problem - CSP)** với các ràng buộc cứng không thể thương lượng:
   - $H_1$: Không chồng lấn với lịch cố định (Lớp học, ca làm, họp, ăn uống).
   - $H_2$: Giờ ngủ được khóa cứng và bảo vệ tuyệt đối (Tối thiểu 6–7 tiếng/đêm).
   - $H_3$: Công việc chỉ được đặt vào các khoảng thời gian trống xác thực (FREE slots).
   - $H_4$: Công việc phải hoàn thành trước thời hạn chót (Deadline) nếu khả thi.
   - $H_5$: Tôn trọng thứ tự phụ thuộc công việc ($A \to B$: $B$ chỉ bắt đầu sau khi $A$ kết thúc).

---

## 2. NGHIÊN CỨU & ĐÁNH GIÁ CÁC GIẢI PHÁP BIỂU DIỄN THỜI GIAN (TIME REPRESENTATION)

Để máy tính có thể tính toán thời gian, ta cần trừu tượng hóa (Abstraction) dòng thời gian thực thành cấu trúc dữ liệu. Có 3 giải pháp kiến trúc chính:

```mermaid
graph TD
    A[Mô Hình Hóa Thời Gian] --> B[Solution 1: Discrete Fixed-Grid]
    A --> C[Solution 2: Continuous Interval List]
    A --> D[Solution 3: Hybrid Interval Tree]
    
    B --> B1[Mảng 672 slots x 15 phút]
    C --> C1[Danh sách các đoạn Start - End]
    D --> D1[Cây phân đoạn Segment/Interval Tree]
```

### Giải pháp 1: Lưới Rời Rạc Cố Định (Discrete Fixed-Size Time Grid - 15 phút / 672 slots)
* **Cơ chế:** Chia tuần học (7 ngày $\times$ 24 giờ) thành mảng 1 chiều gồm $672$ ô (slots), mỗi ô đại diện cho 15 phút:
  $$\text{Slot Index} = \text{day} \times 96 + \text{hour} \times 4 + \lfloor \text{minute} / 15 \rfloor$$
  Mỗi slot lưu một mã trạng thái nhị phân hoặc enum: `FREE`, `OCCUPIED`, `SLEEP`, `BLOCK:task_id`.
* **Ưu điểm:**
  - Cực kỳ trực quan, dễ lập trình và ánh xạ 1-1 với ma trận tính toán tuần cũng như lưới hiển thị trên giao diện Web.
  - Phù hợp với kỹ thuật mảng băm ($O(1)$ lookup thời gian trống).
  - Tự nhiên phù hợp với các phương pháp chia khối làm việc (Pomodoro 25p làm tròn lên 30p, Deep Work 60p, 90p).
* **Nhược điểm:**
  - Hao phí bộ nhớ và phép tính dư thừa khi khoảng thời gian trống kéo dài cả ngày nhưng vẫn phải duyệt qua từng slot 15 phút.
  - Xảy ra sai số làm tròn (Quantization Error / Internal Fragmentation): một task 20 phút buộc phải chiếm trọn 30 phút (lãng phí 10 phút) hoặc 15 phút (bị thiếu 5 phút).
* **Độ phức tạp:** Không gian $O(S)$ với $S = 672$ (cố định). Thời gian kiểm tra khoảng trống độ dài $K$: $O(K)$.

### Giải pháp 2: Danh Sách Khoảng Thời Gian Liên Tục (Continuous Interval List / Event Points)
* **Cơ chế:** Biểu diễn lịch như một tập hợp các đoạn thời gian $[t_{\text{start}}, t_{\text{end}})$. Giờ giấc được tính bằng phút thực tính từ đầu tuần ($t \in [0, 10080]$ phút). Các khoảng rảnh được sinh ra bằng phép bù tập hợp:
  $$\text{FreeIntervals} = [0, 10080) \setminus \bigcup (\text{FixedEvents} \cup \text{SleepWindows})$$
* **Ưu điểm:**
  - Không có sai số làm tròn; lưu trữ chính xác đến từng phút.
  - Bộ nhớ cực kỳ tối ưu: Một ngày rảnh rỗi chỉ tốn đúng 1 đối tượng `Interval(0, 1440)` thay vì 96 phần tử mảng.
  - Dễ dàng tích hợp với các bài toán hình học tính toán (Interval Algebra của Allen).
* **Nhược điểm:**
  - Thao tác chèn/xóa công việc đòi hỏi phép cắt và hợp đoạn phức tạp (Interval Slicing & Merging).
  - Khó chuyển đổi sang ma trận rời rạc hoặc hiển thị trực quan lên lưới Web nếu không có bước Rasterization.
* **Độ phức tạp:** Không gian $O(M)$ với $M$ là số lượng sự kiện cố định ($M \ll 672$). Thời gian tìm kiếm: $O(M \log M)$ (khi sắp xếp).

### Giải pháp 3: Cấu Trúc Cây Phân Đoạn / Cây Khoảng Cách (Interval Tree / Segment Tree)
* **Cơ chế:** Sử dụng cây nhị phân tìm kiếm cân bằng lưu trữ các khoảng thời gian bận/rảnh.
* **Ưu điểm:**
  - Tốc độ truy vấn va chạm (Query Overlap): $O(\log M + K)$ cực nhanh.
  - Khả năng mở rộng tốt cho hệ thống lớn phục vụ hàng ngàn task hoặc lịch trình nhiều tháng.
* **Nhược điểm:**
  - Cực kỳ cồng kềnh, phức tạp hóa không cần thiết cho một bài toán tuần sinh viên ($S=672$).
  - Khó bảo trì và dễ phát sinh lỗi logic biên (Edge cases) trong bài toán lập lịch học đường.

---

> **Quyết định kỹ thuật:** Dựa trên phân tích ưu và nhược điểm của 3 giải pháp trên, phiên bản Baseline chọn **Giải pháp 1 (Lưới 15 phút - 672 slots)** làm nền tảng chính để đảm bảo tính trực quan trong cấu trúc dữ liệu, ăn khớp trực tiếp với ma trận thời gian và giảm thiểu tối đa lỗi tiềm ẩn khi cài đặt.

---

## 3. NGHIÊN CỨU & ĐÁNH GIÁ CÁC GIẢI PHÁP THUẬT TOÁN XẾP LỊCH BASELINE

Nhóm nghiên cứu và thiết kế **5 giải pháp thuật toán khác nhau** thuộc các trường phái tính toán kinh điển (Combinatorial, Heuristic, Exact Math Programming) để so sánh đối chứng.

```mermaid
graph TD
    Engine[Thuật Toán Baseline] --> S1[Solution 1: Brute-Force Permutations]
    Engine --> S2[Solution 2: Backtracking with Pruning]
    Engine --> S3[Solution 3: Classical Greedy Dispatching]
    Engine --> S4[Solution 4: Integer Linear Programming - ILP]
    Engine --> S5[Solution 5: Dynamic Programming / Knapsack]

    S3 --> S3A[3A: Earliest Deadline First - EDF]
    S3 --> S3B[3B: Least Slack Time - LST]
    S3 --> S3C[3C: Weighted Shortest Processing Time - WSPT]
```

---

### 3.1. Giải pháp 1: Vét Cạn Hoán Vị Tuyệt Đối (Pure Brute-Force Permutation)
* **Ý tưởng:** Thử mọi khả năng sắp xếp có thể có trên đời. Sinh toàn bộ $N!$ hoán vị thứ tự của $N$ công việc. Với mỗi hoán vị, thử xếp tuần tự từng task vào mọi vị trí slot trống khả dĩ trên lưới 672 slot.
* **Cơ chế thực thi:**
  1. Sinh tập hoán vị $\mathcal{P} = \text{permutations}(T_1, T_2, \dots, T_N)$.
  2. Với mỗi thứ tự $P \in \mathcal{P}$:
     - Duyệt từng task, thử đặt tại mọi vị trí $s \in [0, 672 - \text{duration}]$.
     - Kiểm tra nếu vi phạm $H_1 \dots H_5$, bỏ qua; nếu hợp lệ, tiến tới task tiếp theo.
  3. Ghi nhận phương án đầu tiên xếp được toàn bộ các task, hoặc phương án có tổng độ trễ nhỏ nhất.
* **Ưu điểm:**
  - Tuyệt đối khách quan; nếu một lời giải hợp lệ tồn tại, thuật toán này chắc chắn tìm ra (Tính toàn vẹn - Completeness $100\%$).
  - Là thước đo chuẩn mực (Ground Truth) để thẩm định mọi thuật toán khác trên tập dữ liệu siêu nhỏ.
* **Nhược điểm:**
  - **Bùng nổ tổ hợp khủng khiếp (Combinatorial Explosion):** Với $N = 10$ task, số hoán vị là $10! \approx 3.6 \times 10^6$. Với mỗi hoán vị, số vị trí đặt là $S^N \approx 672^{10} \approx 10^{28}$. Máy tính sẽ bị tràn bộ nhớ hoặc treo vĩnh viễn.
* **Giới hạn khả thi:** Chỉ chạy được khi $N \le 5$ và số slot trống nhỏ.

---

### 3.2. Giải pháp 2: Quay Lui Có Tỉa Nhánh Cận (Backtracking with Branch-and-Bound)
* **Ý tưởng:** Vét cạn có định hướng thông minh. Xây dựng cây không gian trạng thái; tại mỗi nút quyết định (đặt task $i$ vào slot $s$), kiểm tra các điều kiện cắt tỉa ngay lập tức trước khi đi sâu tiếp.
* **Cơ chế tỉa nhánh (Pruning Conditions):**
  1. **Tỉa theo Ràng buộc Cứng:** Nếu đặt task $i$ tại slot $s$ mà đè lên `OCCUPIED` hoặc `SLEEP` $\implies$ Cắt nhánh ngay.
  2. **Tỉa theo Deadline:** Nếu $s + \text{duration}_i > \text{deadline}_i \implies$ Cắt nhánh ngay.
  3. **Tỉa theo Dung lượng Tổng (Capacity Bounding):** Tại bước thứ $k$, nếu:
     $$\sum_{j=k}^{N} \text{duration}_j > \text{Tổng số slot FREE còn lại từ slot } s \text{ đến cuối tuần}$$
     thì lập tức quay lui vì chắc chắn không đủ thời gian để xếp nốt các task còn lại.
* **Ưu điểm:**
  - Vẫn bảo đảm tìm được lời giải tối ưu (Exact Optimal Solution) mà số nhánh cần duyệt giảm đáng kể so với Brute-force thuần túy.
  - Phù hợp làm công cụ kiểm thử chuẩn (Ground-Truth Validator) cho các bài toán cỡ nhỏ và vừa ($N \le 12$).
* **Nhược điểm:**
  - Trong trường hợp xấu nhất (Worst-case) khi bài toán vô nghiệm (Infeasible), thuật toán vẫn phải vét cạn toàn bộ không gian nhánh trước khi kết luận thất bại $\implies$ Gây hiện tượng trễ cao (High Latency Spike).
* **Độ phức tạp:** Thời gian trung bình $O(b^d)$ (với $b$ là hệ số nhánh sau tỉa, $d = N$). Bộ nhớ $O(N)$ (ngăn xếp đệ quy).

---

### 3.3. Giải pháp 3: Thuật Toán Tham Lam Cổ Điển Theo Luật Phân Phối (Greedy Dispatching Rules)
Đây là họ thuật toán thực tế nhất cho hệ thống Baseline. Thuật toán hoạt động theo nguyên tắc: Sắp xếp danh sách công việc theo một tiêu chí xác định (Sorting Rule), sau đó duyệt tuần tự từng task và đặt vào vị trí trống đầu tiên thỏa mãn (First-Fit Placement).

#### Biến thể 3A: Earliest Deadline First (EDF) + First-Fit (Chuẩn V0 trong Báo cáo §9.3)
* **Cơ chế:**
  - Khóa slot giờ học và giờ ngủ.
  - Sắp xếp task tăng dần theo `deadline`: Task nào đến hạn trước thì được quyền chọn chỗ trước.
  - Đặt task vào dải slot trống `FREE` đầu tiên tìm thấy trước deadline.
* **Ưu điểm:**
  - Nổi tiếng trong lý thuyết lập lịch thời gian thực (Real-time Systems - Jackson's Rule).
  - Tối thiểu hóa độ trễ tối đa ($L_{\max}$) trên hệ thống 1 máy khi không có gián đoạn.
  - Độ phức tạp thời gian thấp: $O(N \log N + N \times S)$ (với $S = 672$ là hằng số).
* **Nhược điểm:**
  - Hoàn toàn phớt lờ độ dài công việc: Một task ngắn hạn chót thứ 3 có thể chiếm mất vị trí đẹp của một task dài 10 tiếng hạn chót thứ 4, dẫn đến task dài bị thiếu chỗ liên tục.
  - Hiện tượng phân mảnh thời gian (Schedule Fragmentation): Tạo ra nhiều khoảng trống vụn vặt 15–30 phút không dùng được.

#### Biến thể 3B: Least Slack Time (LST / Minimum Laxity First) + Best-Fit
* **Cơ chế:**
  - Tính độ trôi tự do (Slack time / Laxity):
    $$\text{Slack}(t) = \text{Deadline}_t - \text{CurrentTime} - \text{Duration}_t$$
  - Task nào có độ trôi ít nhất (nguy cơ trễ hạn cao nhất) được ưu tiên xếp trước.
  - Khi đặt, sử dụng nguyên lý **Best-Fit**: Chọn khoảng trống rảnh có kích thước sát nhất với thời lượng task để tránh làm vỡ các khoảng trống lớn.
* **Ưu điểm:**
  - Thông minh hơn EDF: Cân nhắc đồng thời cả thời hạn chót lẫn độ dài của công việc.
  - Giảm thiểu phân mảnh slot trống hiệu quả hơn First-Fit.
* **Nhược điểm:**
  - Slack time thay đổi động theo thời gian hiện tại, đòi hỏi cập nhật liên tục nếu bài toán mở rộng sang nhiều tuần.
  - Phức tạp hơn EDF một chút trong khâu cài đặt.

#### Biến thể 3C: Weighted Shortest Processing Time (WSPT / Smith's Rule)
* **Cơ chế:**
  - Sắp xếp theo tỷ số: $\text{Ratio} = \frac{\text{Priority}}{\text{Duration}}$.
  - Ưu tiên các việc ngắn nhưng quan trọng để hoàn thành sớm (Quick Wins).
* **Ưu điểm:**
  - Tối đa hóa số lượng task hoàn thành trên một đơn vị thời gian.
* **Nhược điểm:**
  - Rất dễ làm trễ các đồ án lớn dài hạn: Các task lớn 5–10 tiếng có tỷ số thấp sẽ bị đẩy lùi về sát hạn chót và dễ bị rớt lịch.

---

### 3.4. Giải pháp 4: Quy Hoạch Tuyến Tính Nguyên (Integer Linear Programming - ILP / SMT Solver)
* **Cơ chế:** Biến bài toán thành mô hình toán học giải tích chặt chẽ bằng cách sử dụng bộ giải mã nguồn mở (như Google OR-Tools CP-SAT, PuLP, hoặc Z3 SMT):
  - **Biến quyết định nhị phân:** 
    $$x_{i,s} \in \{0, 1\} = 1 \text{ nếu task } i \text{ bắt đầu tại slot } s, \text{ ngược lại } 0$$
  - **Ràng buộc cứng không chồng lấn (Non-overlapping constraint):**
    $$\forall s \in [0, 671], \quad \sum_{i} \sum_{k = \max(0, s - d_i + 1)}^{s} x_{i,k} + \text{Occupied}_s \le 1$$
  - **Ràng buộc thời hạn chót (Deadline constraint):**
    $$x_{i,s} = 0 \quad \forall s > \text{deadline}_i - d_i$$
  - **Hàm mục tiêu (Objective Function):** 
    $$\max \sum_{i} \text{Priority}_i \cdot \sum_s x_{i,s} \quad \text{hoặc} \quad \min \sum_i \text{CompletionTime}_i$$
* **Ưu điểm:**
  - Cho nghiệm tối ưu toàn cục chính xác tuyệt đối mà không cần bất kỳ giả định heuristic nào.
  - Chứng minh được bài toán **vô nghiệm (Infeasible)** một cách toán học chặt chẽ.
* **Nhược điểm:**
  - Cần cài đặt thư viện ngoài (Google OR-Tools), có thể gây khó khăn khi chấm bài hoặc chạy thử trên các máy không có trình biên dịch C++.
  - Khó giải thích logic bằng các quy tắc đời thường.

---

### 3.5. Quyết Định Kiến Trúc Thuật Toán Cho Baseline
Từ phân tích chi tiết về cơ chế và ưu nhược điểm của các giải pháp trên, phiên bản Baseline triển khai theo **Mô hình Đa Thuật Toán (Strategy Pattern)**:
1. **Thuật toán mặc định (Default Engine):** **Giải pháp 3A (Greedy EDF + First-Fit)** — Đây là Baseline B chuẩn đã cam kết trong Báo cáo đề xuất (§9.3), dùng để chạy benchmark chính và đối chứng nghiệm.
2. **Thuật toán so sánh nội bộ (Comparison Engine):** **Giải pháp 3B (Greedy LST + Best-Fit)** — Dùng để kiểm chứng đối sánh hiệu quả giảm phân mảnh slot so với EDF.
3. **Bộ thẩm định chuẩn (Ground-Truth Validator):** **Giải pháp 2 (Backtracking với Pruning)** — Dùng trong bộ kiểm thử Unit Test cho các kịch bản $N \le 8$ để kiểm tra xem thuật toán tham lam có bỏ lỡ nghiệm khả thi nào không.

---

## 4. NGHIÊN CỨU & ĐÁNH GIÁ CÁC CHIẾN LƯỢC PHÂN MẢNH TASK (TASK SPLITTING & CHUNKING)

Một trong những nguyên nhân khiến lịch sinh viên bị vỡ là các công việc có thời lượng lớn (ví dụ: Đồ án 10 tiếng, Ôn thi 4 tiếng) trong khi tuần học chỉ có các khoảng trống rải rác 1–2 tiếng.

```mermaid
graph LR
    Task[Task 180 phút] --> Ch1[Chiến lược 1: Nguyên khối Unsplittable]
    Task --> Ch2[Chiến lược 2: Cắt đều cố định Uniform Chunks]
    Task --> Ch3[Chiến lược 3: Cắt linh hoạt Dynamic Greedy]
    
    Ch1 --> R1[Dễ bị Unplaced vì thiếu khoảng trống 180p liên tục]
    Ch2 --> R2[Cắt thành 3 x 60p, dễ nhét vào lịch]
    Ch3 --> R3[Khoảng rảnh bao nhiêu cắt bấy nhiêu]
```

### Chiến lược 1: Nguyên Khối Không Tách Rời (Strict Non-Preemptive / Atomic)
* **Quy tắc:** Mỗi task là một khối nguyên vẹn, bắt buộc phải tìm được một đoạn `FREE` liên tục đúng bằng `duration_min`. Nếu không có khoảng trống nào đủ dài $\implies$ Đưa vào danh sách `UNPLACED`.
* **Ưu điểm:** Cực kỳ đơn giản; không làm phân mảnh công việc; người học duy trì được sự liền mạch tư duy.
* **Nhược điểm:** Tính khả thi cực thấp khi lịch học dày đặc: Đồ án lớn không thể xếp được vì khoảng trống lớn nhất trong tuần nhỏ hơn thời lượng task.

### Chiến lược 2: Phân Tách Đồng Đều Cố Định (Uniform Fixed-Size Chunking)
* **Quy tắc:** Nếu task có cờ `is_splittable = True` và thời lượng lớn hơn ngưỡng tối đa (ví dụ 90 phút), tự động chia thành các phần bằng nhau, mỗi phần từ 45 đến 90 phút (bội số 15 phút).
  *(Ví dụ: Task 180 phút $\to 2$ phần 90 phút; Task 150 phút $\to 2$ phần 75 phút).*
* **Ưu điểm:** Khối thời gian dự đoán được, cân bằng giữa thời gian tập trung và việc vừa vặn với các khoảng trống.
* **Nhược điểm:** Vẫn có thể bị rớt nếu khoảng trống thực tế trong ngày chỉ có 60 phút nhưng task lại chia thành 75 phút.

### Chiến lược 3: Phân Tách Tham Lam Linh Hoạt (Opportunistic Dynamic Splitting)
* **Quy tắc:** Lấp đầy khoảng trống hiện có. Khi quét gặp một khoảng trống rảnh có độ dài $G \ge \text{min\_chunk}$ (ví dụ $\ge 45$ phút), cắt ngay một phần có độ dài $\min(G, \text{remaining\_duration})$ nhét vào đó, phần còn lại tiếp tục tìm chỗ khác.
* **Ưu điểm:** Tận dụng triệt để 100% dung lượng các khoảng trống; tỷ lệ hoàn thành task cao nhất.
* **Nhược điểm:** Task có thể bị xé vụn thành nhiều mảnh kỳ quặc (ví dụ 45p, 60p, 105p), gây mệt mỏi cho người học nếu không có sự đồng thuận.

> **Quyết định cho Baseline:** Mặc định hỗ trợ **Chiến lược 1 (Nguyên khối)** cho các task thông thường và **Chiến lược 2 (Chia đều cố định 45–90 phút)** nếu cấu hình `is_splittable = True` trong dữ liệu task.

---

## 5. NGHIÊN CỨU & ĐÁNH GIÁ CƠ CHẾ XỬ LÝ SỰ CỐ & DỜI LỊCH (DISRUPTION & RESCHEDULING)

Khi phát sinh một sự kiện đột xuất (ví dụ: Cuộc hẹn khẩn cấp 2 tiếng) hoặc một task làm lố giờ (Task Overrun):

### Giải pháp 1: Tái Tạo Toàn Bộ Lịch (Full Regeneration / Global Rebuild)
* **Cơ chế:** Xóa toàn bộ các block công việc chưa diễn ra từ thời điểm hiện tại (`now`) đến cuối tuần, đánh dấu sự kiện đột xuất vào lưới, và chạy lại thuật toán xếp lịch từ đầu cho tất cả các task chưa hoàn thành.
* **Ưu điểm:** Rất dễ lập trình (chỉ cần gọi lại hàm `solve()`). Đảm bảo tìm được phương án xếp tốt nhất trên toàn cục.
* **Nhược điểm:** **Phá vỡ độ ổn định của lịch trình (Schedule Instability):** Làm xáo trộn cả những task không liên quan, dẫn đến độ ổn định lịch trình bị suy giảm (chỉ số ổn định thực tế sẽ được đo đạc theo công thức tại §9.5).

### Giải pháp 2: Đẩy Dây Chuyền / Tịnh Tiến Thời Gian (Ripple-Shift / Push Delay)
* **Cơ chế:** Khi có sự kiện đè lên Task $A$, đẩy Task $A$ lùi lại ngay sau sự kiện đó. Nếu Task $A$ lại đè lên Task $B$, đẩy tiếp Task $B$ lùi lại phía sau.
* **Ưu điểm:** Giữ nguyên được thứ tự thực hiện các công việc ban đầu.
* **Nhược điểm:** Cực kỳ dễ gây vi phạm giờ học cố định tiếp theo hoặc đẩy các task bị dời vượt qua hạn chót (Deadline Violation).

### Giải pháp 3: Vá Lỗi Cục Bộ Tham Lam (Greedy Local Insertion)
* **Cơ chế:** 
  1. Đóng băng $100\%$ các task không bị sự kiện mới đè lên.
  2. Chỉ nhấc đúng các block công việc bị chồng lấn ra khỏi lưới.
  3. Quét tìm khoảng trống rảnh `FREE` gần nhất tính từ thời điểm hiện tại trở đi mà thỏa mãn hạn chót để đặt các block bị ảnh hưởng vào.
* **Ưu điểm:** Hướng tới mục tiêu bảo toàn độ ổn định lịch trình tối đa (mục tiêu đề tài $\ge 90\%$ theo §2.7, §9.4).
* **Nhược điểm:** Đôi khi không tìm được chỗ mới do các task khác đã khóa cứng không gian rảnh.

> **Định hướng Baseline:** Phiên bản Baseline V0 cung cấp **Giải pháp 1 (Full Regeneration)** làm phương án thuần túy (thuật toán trâu), đồng thời xây dựng hàm đối chứng chuyển sang **Giải pháp 3 (Local Insertion)** để làm bài thí nghiệm đo lường chỉ số ổn định (Stability Metric) trong kịch bản T04!

---

## 6. THIẾT KẾ ĐẦU VÀO & ĐẦU RA CHI TIẾT (INPUT / OUTPUT SCHEMAS)

### 6.1. Chi Tiết Dữ Liệu Đầu Vào (Input Schemas)

#### A. Hồ Sơ Thời Gian Cố Định & Giấc Ngủ (`commitments.json`)
```json
{
  "student_id": "STUDENT_SAMPLE_01",
  "planning_week_start": "2026-11-02T00:00:00",
  "sleep_schedule": {
    "daily_start_time": "23:30",
    "daily_end_time": "06:30",
    "is_hard_lock": true
  },
  "fixed_events": [
    {
      "event_id": "CLASS_MON",
      "title": "Học Lý thuyết Đồ thị",
      "day_of_week": "Monday",
      "start_time": "13:00",
      "end_time": "17:00",
      "category": "ACADEMIC_CLASS"
    },
    {
      "event_id": "MEAL_LUNCH",
      "title": "Ăn trưa & nghỉ trưa",
      "day_of_week": "ALL",
      "start_time": "12:00",
      "end_time": "12:45",
      "category": "MEAL"
    }
  ]
}
```

#### B. Danh Sách Công Việc Cần Xếp Lịch (`tasks.json`)
```json
[
  {
    "task_id": "MATH-1",
    "title": "Ôn tập Quiz Toán giữa kỳ",
    "duration_min": 120,
    "deadline_day": "Wednesday",
    "deadline_time": "13:00",
    "priority": 5,
    "is_splittable": true,
    "min_chunk_min": 45,
    "depends_on": []
  },
  {
    "task_id": "PRJ-3",
    "title": "Kiểm thử đồ án lập trình",
    "duration_min": 120,
    "deadline_day": "Sunday",
    "deadline_time": "23:59",
    "priority": 5,
    "is_splittable": true,
    "min_chunk_min": 45,
    "depends_on": ["PRJ-1", "PRJ-2"]
  }
]
```

---

### 6.2. Chi Tiết Dữ Liệu Đầu Ra (Output Schemas)

#### A. Lịch Trình Tuần Hoàn Chỉnh (`schedule_output.json`)
```json
{
  "status": "SUCCESS",
  "solver_used": "GREEDY_EDF_FIRST_FIT",
  "execution_time_ms": "<float: giá trị đo đạc bằng time.perf_counter()>",
  "summary": {
    "total_tasks_requested": 9,
    "tasks_placed": 9,
    "tasks_unplaced": 0,
    "hard_constraint_violations": 0,
    "free_slots_remaining": "<int: số slot còn trống thực tế>"
  },
  "blocks": [
    {
      "task_id": "MATH-1",
      "title": "Ôn tập Quiz Toán giữa kỳ",
      "day": "Monday",
      "start_time": "07:30",
      "end_time": "09:00",
      "start_slot": 30,
      "end_slot": 36,
      "chunk_index": 1,
      "total_chunks": 2
    }
  ]
}
```

#### B. Báo Cáo Không Thể Xếp & Cảnh Báo Quá Tải (`overload_report.json`)
Phân biệt minh bạch 2 trường hợp lỗi toán học theo đúng chuẩn mục §6.5 của báo cáo:
1. **Lỗi Thiếu Hụt Dung Lượng (Capacity Shortage - "Not enough time"):** Tổng thời lượng các task có hạn chót trước $D$ lớn hơn tổng thời gian trống khả dụng trước $D$. Đây là bằng chứng toán học chứng minh bài toán **vô nghiệm**.
2. **Lỗi Phân Mảnh Chỗ Trống (Fragmentation Failure - "No schedule found"):** Tổng thời gian trống vẫn lớn hơn thời lượng task, nhưng không có khoảng trống nào liên tục đủ dài để chứa task nguyên khối.

```json
{
  "error_type": "CAPACITY_SHORTAGE",
  "message": "Không đủ thời gian trước hạn chót Thứ Ba 23:59",
  "deadline": "Tuesday 23:59",
  "total_free_minutes_available": 1365,
  "total_planned_work_minutes": 1470,
  "shortage_minutes": 105,
  "suggested_actions": [
    "Dời hạn chót của task có độ ưu tiên thấp",
    "Cho phép chia nhỏ task (Bật cờ is_splittable)"
  ]
}
```

---

## 7. THIẾT KẾ GIAO DIỆN & TƯƠNG TÁC WEB DÀNH RIÊNG CHO BASELINE (UI/UX SPECIFICATION)

### 7.1. Định Vị Phạm Vi: UI/UX Baseline (V0) vs. UI/UX Hoàn Chỉnh (Tương Lai)

Để đảm bảo tính chuẩn xác tuyệt đối trong phương pháp luận nghiên cứu của môn Tư Duy Tính Toán, nhóm phân định ranh giới rạch ròi giữa **Giao diện Baseline (Hiện tại)** và **Giao diện Sản phẩm Hoàn chỉnh (Tương lai)**:

```mermaid
graph LR
    subgraph BaselineUI["GIAO DIỆN BASELINE V0 (HIỆN TẠI)"]
        direction TB
        B1["Bàn Thử Nghiệm Kỹ Thuật (Workbench)"]
        B2["Nhập liệu Form cấu trúc & JSON/CSV"]
        B3["Lưới Lịch 672 slots (15 phút) tất định"]
        B4["Bảng Thẻ Đo Chỉ Số Thuật Toán (KPIs)"]
        B5["Hộp Kiểm Thử Biến Cố & Xung Đột"]
    end

    subgraph FutureUI["GIAO DIỆN HOÀN CHỈNH V1-V3 (TƯƠNG LAI)"]
        direction TB
        F1["Chatbox AI Đọc Ngôn Ngữ Tự Nhiên (M1)"]
        F2["Thanh Trượt Nhịp Sinh Học & Năng Lượng"]
        F3["Khảo Sát Hồi Cứu Tuần & Đo Mệt Mỏi (EMA)"]
        F4["Gợi Ý Tâm Lý Học (Momentum Priming)"]
        F5["Mobile App & Đồng Bộ 2 Chiều Google Cal"]
    end
```

* **Giao diện Baseline (V0) — Đang triển khai:**
  - **Định vị:** Là một trang **Bảng điều khiển thử nghiệm kỹ thuật (Technical Benchmark Workbench)** 1 màn hình duy nhất, giúp người dùng nhập thời khóa biểu cứng, danh sách bài tập, và bấm nút để thuật toán cổ điển tự động xếp lịch trên lưới 672 ô (mỗi ô 15 phút từ Thứ 2 đến Chủ nhật).
  - **Cách nhập công việc:** Form nhập liệu cứng (Tên, số phút, hạn chót, độ ưu tiên, cờ cắt nhỏ) hoặc tải tệp `JSON`/`CSV`. Không có tính năng đoán mò; dữ liệu nhập vào thế nào thì thuật toán xử lý chính xác tuyệt đối như thế.
  - **Xử lý thời lượng & phân loại:** Giữ nguyên số phút ước tính thô $T_{\text{estimate}}$ (làm tròn bội số 15p), chỉ có mã định danh `task_id` và `priority` (1–5).
  - **Thiết lập giờ ngủ & nhịp sinh học:** Giờ ngủ được khóa cứng bảo vệ. Tuyệt đối **không có** thanh trượt nhịp sinh học, không có phân loại Deep/Medium/Shallow work, không tự động chèn 15 phút nghỉ giải lao.
  - **Mục đích chính:** Nhập bài toán $\to$ Chạy thuật toán cổ điển (EDF, LST, Vét cạn) $\to$ Xem lỗi xung đột $\to$ Đo thời gian thực thi (ms) và kiểm chứng tính đúng đắn ($C_{\text{hard}} = 0$).
* **Giao diện Hoàn chỉnh (V1–V3) — Để dành cho giai đoạn sau:**
  - Tích hợp Khung Chat AI (NLP Module M1) đọc câu tự do tiếng Việt hoặc giọng nói, tự động nhân hệ số đệm tâm lý ($\times 1.2 / \times 1.35$), phân loại `Deep/Medium/Shallow Work`, thanh chọn khung giờ vàng sinh học (Sáng sớm vs Cú đêm), tự động chèn 15p nghỉ, khảo sát hồi cứu cuối tuần (Sunday Retrospective & Fatigue EMA), gợi ý tâm lý học (Momentum Priming) và đồng bộ 2 chiều Google Calendar trên Mobile App.

---

### 7.2. Nguyên Tắc Thiết Kế Giao Diện Baseline
1. **Chuẩn xác về dữ liệu (Data Precision):** Mỗi khối thời gian trên màn hình phải khớp chính xác 1-1 với mảng 672 slot trong mã nguồn backend (bước nhảy 15 phút).
2. **Minh bạch thuật toán (Algorithmic Transparency):** Người dùng bấm nút xếp lịch là thấy ngay lịch được sinh ra theo quy tắc nào (việc hạn chót gần nhất xếp trước, hoặc độ trôi ít nhất xếp trước).
3. **Đo đạc định lượng rõ ràng (Metric Observability):** Bắt buộc phải có các thẻ đo: Số vi phạm ràng buộc cứng (phải $= 0$), tỷ lệ đạt deadline (%), và thời gian chạy thực tế (mili-giây).
4. **Không tính năng thừa (No Feature Creep):** Loại bỏ toàn bộ các chi tiết trang trí không phục vụ cho việc kiểm thử thuật toán.

---

### 7.3. Nghiên Cứu Giải Pháp Công Nghệ Web (Web Tech Stack Options)

Nhóm xem xét 3 giải pháp công nghệ để xây dựng giao diện Web cho Baseline:

```mermaid
graph TD
    WebOptions[Lựa Chọn Công Nghệ Web] --> Opt1[Option 1: Modern Full-Stack Web<br>React/Vue + Tailwind CSS + FastAPI]
    WebOptions --> Opt2[Option 2: Python Rapid Web<br>Streamlit / NiceGUI]
    WebOptions --> Opt3[Option 3: Lightweight Single-Page App<br>Vanilla JS + HTML5/Tailwind CDN + FastAPI]

    Opt1 --> R1[Chuyên nghiệp, tương tác lưới lịch mượt mà, tách biệt Frontend-Backend]
    Opt2 --> R2[Thuần Python, dựng nhanh để kiểm thử nội bộ]
    Opt3 --> R3[Nhẹ, giao diện đẹp bằng Tailwind Grid, không cần cài Node.js cồng kềnh]
```

* **Option 1 — React/Vite + Tailwind CSS (Frontend) + FastAPI (Backend):** Giao diện lưới lịch tùy biến cực kỳ mượt mà (CSS Grid/Canvas hoặc FullCalendar), hỗ trợ tốt Modal pop-up và Toast notification; tuy nhiên đòi hỏi cài đặt cả môi trường Node.js lẫn Python.
* **Option 2 — Pure Python Streamlit Dashboard:** Cài đặt nhanh (`pip install streamlit`), thuần Python; nhưng hạn chế về khả năng tùy biến sâu lưới lịch 672 slot và tương tác chủ yếu theo luồng tuần tự trên sidebar.
* **Option 3 — Lightweight Single-Page App (HTML5/Tailwind CDN + Vanilla JS + FastAPI):** Kết hợp ưu điểm của cả hai: Backend FastAPI gọn nhẹ phục vụ trực tiếp trang HTML5/Tailwind CSS hiện đại, tương tác DOM mượt mà qua REST API mà không cần cài đặt `node_modules` phức tạp.

---

### 7.4. Các Phương Án Bố Cục Giao Diện Baseline (UI Layout Options)

Nhóm nghiên cứu **4 phương án bố cục màn hình chuyên biệt** để lựa chọn cho Baseline:

```mermaid
graph TD
    UIOptions[Các Phương Án Bố Cục Giao Diện Baseline] --> Opt1[Phương Án 1: Bảng Điều Khiển Kỹ Thuật 2 Cột<br>Technical Benchmark Dashboard]
    UIOptions --> Opt2[Phương Án 2: Lưới Lịch Toàn Màn Hình + Hộp Nhập Nổi<br>Grid-First Minimalist Workbench]
    UIOptions --> Opt3[Phương Án 3: Giao Diện So Sánh Song Song 2 Lịch<br>Dual-Algorithm Comparative View]
    UIOptions --> Opt4[Phương Án 4: Quy Trình Hướng Dẫn 4 Bước Tuần Tự<br>Step-by-Step Wizard]
```

#### Phương Án 1: Bảng Điều Khiển Kỹ Thuật 2 Cột (Technical Benchmark Dashboard)
> **Định vị:** Phương án tiêu chuẩn, gói gọn mọi chức năng trong 1 màn hình duy nhất (All-in-one). Cột trái (35%) là nơi nhập dữ liệu và điều khiển; cột phải (65%) là nơi hiển thị lưới lịch và kết quả đo đạc.

```
+========================================================================================================================+
| ⚡ SMARTSCHEDULE BASELINE (V0) — BENCHMARK WORKBENCH       | [ 📂 Nạp Dữ Liệu Mẫu (Demo) ] [ 🔄 Xóa Sạch ] [ 💾 Xuất .ICS ] |
+========================================================================================================================+
| CỘT TRÁI: DỮ LIỆU ĐẦU VÀO & ĐIỀU KHIỂN (35%)               | CỘT PHẢI: KẾT QUẢ XẾP LỊCH & ĐO ĐẠC ĐỊNH LƯỢNG (65%)        |
+------------------------------------------------------------+-----------------------------------------------------------+
| [Tab 1: Thêm Task]  [Tab 2: Lịch Cố Định & Ngủ]  [Tab 3: Test]| 📊 THẺ ĐO LƯỜNG HIỆU NĂNG (BENCHMARK METRICS):            |
|                                                            | +-----------------+------------------+------------------+ |
| 📝 THÔNG TIN TASK MỚI:                                     | | Lỗi Vi Phạm H1-H5| Kịp Deadline     | Thời Gian Giải   | |
| * Mã Task:     [ MATH-1              ]                     | |      0 lỗi      |     100.0%       |  -- ms (thực đo)  | |
| * Thời lượng:  [ 120 ] phút (Quy đổi: 8 slots)             | +-----------------+------------------+------------------+ |
| * Deadline:    [ Thứ Tư      v ] Lúc: [ 13:00 v ]          |                                                           |
| * Độ ưu tiên:  ( ) 1  ( ) 2  ( ) 3  (o) 4  ( ) 5           | 📅 LƯỚI LỊCH BIỂU TUẦN 7 NGÀY (672 SLOTS x 15 PHÚT):       |
| * Cắt nhỏ task:[X] Cho phép -> Nhỏ nhất: [ 45 ] phút       | Khung giờ | Thứ 2   | Thứ 3   | Thứ 4   | Thứ 5...| CN  |
| * Phụ thuộc:   [ Không có                         v ]      | ----------+---------+---------+---------+---------+-----|
| [ ➕ Thêm Vào Hàng Đợi ]                                   | 00:00-06:30| [SLEEP] | [SLEEP] | [SLEEP] | [SLEEP] | ... |
|                                                            | 06:30-07:00|  FREE   |  FREE   |  FREE   |  FREE   | ... |
| 📋 HÀNG ĐỢI TASK HIỆN TẠI (QUEUE - 9 tasks):               | 07:00-07:30| [MEAL]  | [MEAL]  | [MEAL]  | [MEAL]  | ... |
| 1. MATH-1 | 120p | Hạn: T4 13:00 | Ưu tiên 5 [✏️][🗑️]     | 07:30-09:00| [MATH-1]|  FREE   | [PRJ-1] |  FREE   | ... |
| 2. LAB-1  |  60p | Hạn: T3 23:59 | Ưu tiên 3 [✏️][🗑️]     | 09:00-10:30| [MATH-1]|  FREE   | [PRJ-2] |  FREE   | ... |
| 3. PRJ-1  | 120p | Hạn: CN 23:59 | Ưu tiên 5 [✏️][🗑️]     | 13:00-17:00| [CLASS] |  FREE   | [CLASS] |  FREE   | ... |
| ...                                                        | ...       | ...     | ...     | ...     | ...     | ... |
|                                                            | 23:30-24:00| [SLEEP] | [SLEEP] | [SLEEP] | [SLEEP] | ... |
| ⚙️ BỘ CHỌN THUẬT TOÁN BASELINE:                            |                                                           |
| (o) Tham lam Earliest Deadline First (EDF) [Mặc định]      | 🔴 CHÚ THÍCH MÃ MÀU TRẠNG THÁI SLOT:                      |
| ( ) Tham lam Least Slack Time (LST)                        | 🟪 Tím: Giờ ngủ bảo vệ (SLEEP)                            |
| ( ) Vét cạn Quay lui (Backtracking - Thử nghiệm nhỏ <= 8)  | 🟥 Đỏ: Giờ học cố định / Ăn uống (OCCUPIED)               |
|                                                            | 🟩 Xanh: Task đã được xếp (BLOCK:task_id)                 |
| >>> 🚀 [ CHẠY THUẬT TOÁN XẾP LỊCH (SOLVE) ] <<<            | ⬜ Trắng/Xám: Thời gian rảnh khả dụng (FREE)              |
+------------------------------------------------------------+-----------------------------------------------------------+
| ⚠️ KHUNG CẢNH BÁO QUÁ TẢI (Hiện khi phát hiện xung đột hoặc không xếp hết task):                                       |
| [!] CẢNH BÁO: Phát hiện thiếu hụt 105 phút rảnh trước hạn chót Thứ Ba 23:59. Có 1 task không thể xếp (UNPLACED).         |
+========================================================================================================================+
```
* **Ưu điểm:** Bố cục rõ ràng, trực quan; người dùng thấy ngay mối quan hệ nhân quả: Đổi dữ liệu bên trái $\to$ Bấm nút $\to$ Lịch bên phải đổi màu ngay lập tức mà không cần chuyển trang.
* **Nhược điểm:** Màn hình chứa nhiều thông tin cùng lúc; trên thiết bị di động cần cuộn dọc.
* **Đánh giá:** **Lựa chọn chuẩn xác và khuyên dùng số 1 cho bản Baseline.**

#### Phương Án 2: Lưới Lịch Toàn Màn Hình + Popup Nhập Liệu (Grid-First Minimalist Workbench)
> **Định vị:** Dành cho người thích sự tối giản, lấy Lưới Lịch làm trung tâm, các thao tác nhập liệu thực hiện qua cửa sổ Popup (Modal) hoặc khay trượt (Drawer).
* **Sơ đồ bố cục:**
  - Màn hình dành trọn không gian hiển thị Lưới Lịch 7 ngày.
  - Phía trên có thanh công cụ tinh gọn gồm các nút: `[ + Thêm Task ]`, `[ Cài Đặt Giờ Ngủ/Học ]`, `[ Chạy EDF ]`, `[ Xuất File ]`.
  - Khi bấm `[ + Thêm Task ]`, một hộp thoại nhỏ hiện lên giữa màn hình để nhập thông tin, nhập xong bấm `Lưu` là popup đóng lại và task xuất hiện trên lịch. Danh sách task chưa xếp có thể nằm ở khay kéo dưới đáy màn hình.
* **Ưu điểm:** Lưới lịch rất to, thoáng đãng, dễ nhìn từng khung giờ 15 phút.
* **Nhược điểm:** Mỗi lần thêm hoặc sửa task lại phải đóng/mở popup, thao tác nhập liên tiếp nhiều bài tập tốn nhiều lần click chuột hơn Phương án 1.

#### Phương Án 3: Giao Diện So Sánh Song Song 2 Lịch (Dual-Algorithm Comparative View)
> **Định vị:** Chuyên biệt phục vụ cho việc **thuyết trình, báo cáo khoa học trước giảng viên**, chứng minh sự khác biệt định lượng giữa các giải pháp thuật toán.
* **Sơ đồ bố cục:**
  - Chia đôi màn hình để đặt 2 bảng lịch cạnh nhau:
    * Bảng lịch bên trái: Sinh ra từ **Thuật toán 1: Tham lam EDF (First-Fit)**.
    * Bảng lịch bên phải: Sinh ra từ **Thuật toán 2: Tham lam LST (Best-Fit)** (hoặc đặt Lịch trước sự cố cạnh Lịch sau sự cố).
  - Bảng đối chiếu chỉ số ở giữa/dưới chân màn hình: So sánh trực tiếp thời gian giải (ms), tỷ lệ đạt hạn chót và mức độ phân mảnh slot rảnh.
* **Ưu điểm:** Giúp giảng viên và hội đồng thấy ngay sự khác nhau giữa 2 tư duy thuật toán khi chấm đồ án môn Tư Duy Tính Toán.
* **Nhược điểm:** Mỗi bảng lịch bị hẹp lại; phù hợp làm chế độ demo nghiên cứu hơn là giao diện sử dụng hàng ngày.

#### Phương Án 4: Quy Trình Hướng Dẫn 4 Bước Tuần Tự (Step-by-Step Wizard / Stepper)
> **Định vị:** Chia nhỏ quy trình thành 4 bước tuần tự, mỗi màn hình chỉ tập trung vào một thao tác.
* **Sơ đồ luồng:** `[ Bước 1: Khóa Lịch Bận & Giờ Ngủ ]` $\to$ `[ Bước 2: Nhập Danh Sách Task ]` $\to$ `[ Bước 3: Chọn Thuật Toán & Giải ]` $\to$ `[ Bước 4: Xem & Xuất Lịch Tuần ]`.
* **Ưu điểm:** Rất thoáng đãng, không bị ngợp thông tin cho người mới bắt đầu.
* **Nhược điểm:** Khi muốn thử tinh chỉnh thông số 1 task để kiểm thử lại thuật toán, người dùng phải bấm "Back" và "Next" qua lại giữa các bước.

---

### 7.5. Các Phương Án Về Cách Thức Nhập Liệu (Input Interaction Options)

```mermaid
graph LR
    InputMethods[Phương thức Nhập liệu] --> In1[Option A: Form truyền thống + Modal]
    InputMethods --> In2[Option B: Bảng nhập nhanh dạng Spreadsheet]
    InputMethods --> In3[Option C: Cú pháp rút gọn nhanh Text-Chips]
```

* **Option A — Biểu Mẫu Nhập Liệu Chuẩn (Standard Web Form & Modals):** Điền vào các ô nhập (Tên, số phút, chọn ngày deadline từ dropdown, chọn độ ưu tiên 1–5). Dễ hiểu nhất, ngăn chặn triệt để lỗi nhập sai định dạng.
* **Option B — Bảng Dữ Liệu Tương Tác Trực Tiếp (Spreadsheet Inline Table):** Bảng gồm các cột `Tên Task | Thời lượng | Hạn chót | Ưu tiên | Cắt nhỏ?`, click đúp vào từng dòng để gõ nhanh hàng loạt bài tập như trên Excel.
* **Option C — Cú Pháp Rút Gọn Nhanh (Fast Quick-Add Chips):** Gõ dòng cú pháp định dạng cố định không dùng AI (ví dụ: `Toan 120m t4:13:00 p5`), hệ thống dùng biểu thức chính quy (Regex) tách trực tiếp thành các thuộc tính.

> **Đề xuất tổng hợp (Hybrid Recommendation) cho Giao diện Baseline:**  
> Nhóm áp dụng **Phương Án 1 (Bảng Điều Khiển Kỹ Thuật 2 Cột)** kết hợp **Form chuẩn (Option A)** làm giao diện chính thức cho Baseline V0, đồng thời tích hợp nút bật/tắt **Chế độ So sánh Song song (Phương Án 3)** để phục vụ trực tiếp cho việc demo đối chứng thuật toán khi báo cáo đồ án.

---

### 7.6. Danh Mục Chức Năng Cụ Thể & Hệ Thống Màu Sắc Trạng Thái

Màn hình Baseline Workbench cung cấp đầy đủ 9 nhóm chức năng kỹ thuật:
1. **Nút "Nạp dữ liệu mẫu" (1-Click Preset):** Nạp sẵn bộ thời khóa biểu và bài tập mẫu chuẩn để kiểm thử thuật toán ngay mà không cần gõ tay từng mục.
2. **Khóa Ràng Buộc Cứng (Hard Constraints):**
   - Khóa khung giờ ngủ (ví dụ: 23:30 – 06:30) $\to$ Các ô chuyển thành màu tím (`SLEEP`), thuật toán tuyệt đối không bao giờ xếp bài tập vào đây.
   - Khóa giờ học cố định trên lớp, giờ ăn cơm, họp nhóm $\to$ Các ô chuyển thành màu đỏ/cam (`OCCUPIED`).
3. **Form nhập bài tập cần làm & Hàng đợi (Task Queue):**
   - Điền tên bài tập, số phút cần làm (có nút cộng nhanh `+15m`, `+30m`, `+60m` và tự động quy đổi sang số slot 15 phút), hạn chót (Thứ + Giờ) hoặc tùy chọn không có hạn chót, độ ưu tiên (1 đến 5), cờ cho phép cắt nhỏ (`is_splittable` kèm `min_chunk_min`), và danh sách task phụ thuộc (`depends_on`).
   - Danh sách hàng đợi hiển thị rõ các task đã nhập, hỗ trợ nút sửa (`✏️`) và xóa (`🗑️`) trực tiếp.
4. **Bộ chọn thuật toán Baseline:** Cho phép chọn giữa *Thuật toán Tham lam EDF (hạn gần xếp trước)*, *Thuật toán Tham lam LST (độ trôi ít xếp trước)*, hoặc *Vét cạn Backtracking*.
5. **Nút "🚀 Chạy Thuật Toán Xếp Lịch (Solve)":** Bấm nút để thuật toán quét lưới 672 slot và phân bổ bài tập vào các khoảng trống hợp lệ.
6. **Lưới Lịch Tuần 7 Ngày (672 ô $\times$ 15 phút) & Bảng Mã Màu Chuẩn (WCAG AA):**
   - Hỗ trợ chuyển đổi độ phân giải hiển thị (`15 phút` / `30 phút` / `1 giờ`) và nút ẩn/hiện khung giờ ngủ.
   - Hệ thống mã màu trực quan:
     * 🟪 **Tím (`#334155` - Slate/Indigo):** Giờ ngủ được khóa bảo vệ (`SLEEP`).
     * 🟥 **Đỏ (`#E11D48` - Rose) / Cam (`#D97706` - Amber):** Lớp học cố định / Sinh hoạt ăn uống (`OCCUPIED`).
     * 🟩 **Xanh lá (`#059669` - Emerald):** Giờ làm bài tập đã xếp thành công (`BLOCK:task_id`).
     * ⬜ **Trắng/Xám (`#F8FAFC` - Slate-50):** Thời gian rảnh rỗi khả dụng (`FREE`).
     * 🔴 **Đỏ đậm (`#DC2626` - Red):** Cảnh báo xung đột / Task chưa xếp được (`UNPLACED`).
   - Khi rê chuột (hover) vào một ô công việc màu xanh, hiển thị Tooltip giải thích minh bạch: *Tên công việc, khung giờ, hạn chót, và lý do được thuật toán chọn đặt tại vị trí đó*.
7. **Thẻ đo lường hiệu năng kỹ thuật (Benchmark KPIs):**
   - Số lỗi vi phạm ràng buộc cứng ($C_{\text{hard}}$, bắt buộc $= 0$).
   - Tỷ lệ hoàn thành kịp deadline ($R_{\text{deadline}}$, tính theo %).
   - Thời gian máy tính giải bài toán ($T_{\text{exec}}$, đo thực tế bằng mili-giây).
   - Số lượng slot trống còn lại trong tuần.
8. **Khung cảnh báo thiếu giờ toán học & Hộp thử nghiệm sự cố đột xuất:**
   - Nếu tổng thời lượng việc vượt quá quỹ thời gian rảnh, hiện khung cảnh báo chỉ rõ số phút bị thiếu hụt trước hạn chót và liệt kê các task `UNPLACED`.
   - Tab "Test Sự Cố" cho phép chèn một sự kiện bận bất ngờ vào lịch đã xếp để quan sát trực tiếp sự khác biệt giữa *Tái tạo toàn bộ lịch (Full Rebuild)* và *Vá lỗi cục bộ (Local Insertion)*.
9. **Xuất dữ liệu (Export):** Tải lịch về máy dưới định dạng `.json` (phục vụ kiểm thử tự động), `.csv` (bảng biểu), hoặc `.ics` (tệp iCalendar chuẩn để nhập vào Google Calendar / Apple Calendar).

---

### 7.7. Quy Trình Tương Tác Người Dùng Chuẩn Xác Trên Baseline (Step-by-Step Flows)

Mọi thao tác của người dùng trên phiên bản Baseline đều thuần túy mang tính kỹ thuật và tất định:

```mermaid
flowchart TD
    S1[1. Khóa Giờ Ngủ & Lịch Cố Định] --> S2[2. Nhập Danh Sách Task Cần Xếp]
    S2 --> S3[3. Chọn Thuật Toán Cổ Điển: EDF / LST / Backtracking]
    S3 --> S4[4. Bấm Chạy Xếp Lịch]
    S4 --> S5{Thuật toán xếp hết task?}
    S5 -->|Có| S6[Hiển thị Lưới Lịch Xanh Lá + Tooltip Giải Thích]
    S5 -->|Không| S7[Hiện Cảnh Báo Thiếu Giờ Toán Học + Đưa Task Vào UNPLACED]
    S6 --> S8[5. Thử Nghiệm Sự Cố Đột Xuất Hoặc Xuất File .ICS / .JSON]
    S7 --> S8
```

1. **Bước 1 — Khóa Ràng Buộc Cứng (Hard Constraints):** Người dùng nhập khung giờ ngủ (ví dụ: 23:30 – 06:30) và các buổi học cố định trên lớp *(hoặc bấm 1 click vào nút "Nạp dữ liệu mẫu" để nạp bộ dữ liệu chuẩn)*. Các ô tương ứng trên lưới lập tức chuyển sang trạng thái khóa (`SLEEP` và `OCCUPIED`).
2. **Bước 2 — Nhập Thông Số Task (Task Ingestion):** Nhập tên bài tập, thời lượng ước tính gốc, hạn chót nộp bài, độ ưu tiên (1–5), tùy chọn chia nhỏ và phụ thuộc công việc rồi thêm vào hàng đợi.
3. **Bước 3 — Chọn Thuật Toán Xếp Lịch:** Click chọn thuật toán muốn thực nghiệm (`Greedy EDF`, `Greedy LST`, hoặc `Backtracking`).
4. **Bước 4 — Bấm Nút "🚀 Chạy Thuật Toán Xếp Lịch":** Hệ thống quét các slot `FREE`, điền các khối công việc màu xanh lá (`BLOCK`) lên lưới lịch tuần và cập nhật tức thì các thẻ chỉ số KPI. Người dùng rê chuột vào từng khối để kiểm tra thông tin chi tiết và lý do xếp lịch.
5. **Bước 5 — Kiểm Thử Tình Huống Xung Đột & Sự Cố (Nếu Cần):** Quan sát báo cáo thiếu hụt thời gian nếu quá tải, hoặc thử chèn một sự kiện đột xuất để kiểm tra tính ổn định khi dời lịch.
6. **Bước 6 — Xuất Kết Quả:** Tải file `.ics` hoặc `.json` về máy để lưu trữ và nghiệm thu.

---

## 8. KIẾN TRÚC HỆ THỐNG MÃ NGUỒN & CẤU TRÚC DỰ ÁN

Hệ thống Baseline được thiết kế theo cấu trúc module hóa phân tầng (Layered Architecture), tách biệt hoàn toàn giữa Tầng Giao diện Web / CLI và Tầng Động cơ Thuật toán Cốt lõi:

```
+-------------------------------------------------------------------------+
|            TẦNG GIAO DIỆN & THỰC THI (PRESENTATION & CLI LAYER)         |
|   web_app (Web UI Workbench)  /  main.py (CLI)  /  benchmark_runner.py  |
+-------------------------------------------------------------------------+
                                    │
                                    ▼
+-------------------------------------------------------------------------+
|                    TẦNG ĐIỀU PHỐI (ORCHESTRATION LAYER)                 |
|              controller.py: Quản lý luồng xử lý và đo đạc               |
+-------------------------------------------------------------------------+
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
+-----------------------------------+ +-----------------------------------+
|     TẦNG QUẢN LÝ LƯỚI & RÀNG BUỘC | |     TẦNG THUẬT TOÁN ĐA GIẢI PHÁP  |
|       (GRID & CONSTRAINT LAYER)   | |      (SCHEDULING STRATEGY LAYER)  |
| grid_manager.py:                  | | solvers/                          |
| - Mảng 672 slots (15 phút)        | |  ├── base_solver.py (Interface)   |
| - Khóa SLEEP / OCCUPIED           | |  ├── greedy_edf.py (Baseline B)   |
| - Kiểm tra va chạm ràng buộc cứng | |  ├── greedy_lst.py (Biến thể)     |
|                                   | |  └── backtracking.py (Vét cạn)    |
+-----------------------------------+ +-----------------------------------+
                                    │
                                    ▼
+-------------------------------------------------------------------------+
|                     TẦNG MÔ HÌNH DỮ LIỆU & TIỆN ÍCH                     |
|           models.py (Data Classes)  /  utils.py (Chuyển đổi giờ)        |
+-------------------------------------------------------------------------+
```

### Cấu Trúc File Chi Tiết
```text
group03-smartschedule-baseline/
│
├── README.md                          # Hướng dẫn cài đặt, chạy Web UI và kiểm thử
├── requirements.txt                   # Danh sách thư viện (fastapi, uvicorn / streamlit, pydantic, pytest)
├── run_app.bat                        # Script khởi động nhanh ứng dụng trên Windows
├── run_tests.bat                      # Script chạy toàn bộ test tự động trên Windows
│
├── data/                              # Dữ liệu phục vụ kiểm thử và Demo Preset
│   ├── sample_week_commitments.json   # Lịch thời khóa biểu và giấc ngủ mẫu
│   ├── sample_week_tasks.json         # Danh sách 9 task bài tập mẫu
│   └── test_scenarios/                # Bộ dữ liệu 10 kịch bản T01 - T10
│       ├── t01_normal_feasible.json
│       ├── t02_overlapping_deadlines.json
│       ├── t03_large_unsplittable.json
│       ├── t04_event_disruption.json
│       └── t06_overload_capacity.json
│
├── src/                               # Toàn bộ mã nguồn động cơ Baseline
│   ├── __init__.py
│   ├── models.py                      # Pydantic Schemas (Task, Event, ScheduleBlock)
│   ├── utils.py                       # Chuyển đổi timestamp <-> slot index (0..671)
│   ├── grid_manager.py                # Quản trị lưới 672 slots, khóa giờ ngủ, check va chạm
│   ├── metrics.py                     # Đo đạc Hard Violations, Deadline Rate, Latency, Stability
│   ├── exporter.py                    # Xuất kết quả ra định dạng JSON, CSV và iCalendar (.ics)
│   │
│   └── solvers/                       # Thư viện thuật toán theo mẫu Strategy Pattern
│       ├── __init__.py
│       ├── base_solver.py             # Lớp trừu tượng BaseScheduler
│       ├── greedy_edf.py              # Thuật toán chính: Earliest Deadline First
│       ├── greedy_lst.py              # Thuật toán biến thể: Least Slack Time
│       ├── backtracking.py            # Thuật toán vét cạn có tỉa nhánh
│       └── local_repair.py            # Thuật toán vá lỗi cục bộ khi có sự cố
│
├── web/                               # Tầng Giao diện Web Baseline Workbench
│   ├── api.py                         # REST API kết nối Giao diện Web với Core Engine
│   ├── index.html                     # Giao diện Bảng điều khiển 2 cột & Lưới lịch 672 slots
│   └── app.js                         # Xử lý tương tác người dùng, render lịch và hiển thị KPIs
│
├── tests/                             # Bộ kiểm thử tự động PyTest
│   ├── test_time_grid.py              # Kiểm tra khởi tạo 672 slots và khóa giờ
│   ├── test_constraints.py            # Kiểm tra đảm bảo 0 vi phạm giờ học / ngủ
│   ├── test_edf_solver.py             # Kiểm tra logic thuật toán EDF
│   └── test_scenarios_t01_t10.py      # Chạy kiểm thử tự động toàn bộ 10 kịch bản
│
├── benchmark_runner.py                # Chạy đo đạc thời gian, bộ nhớ, chỉ số T01-T10
└── main.py                            # Điểm thực thi dòng lệnh (CLI Runner)
```

---

## 9. KẾ HOẠCH KIỂM THỬ ĐỐI CHỨNG VÀ BỘ CHỈ SỐ ĐO LƯỜNG (BENCHMARK & METRICS)

### 9.1. Bộ Chỉ Số Đánh Giá Đo Lường Khoa Học (Quantitative Metrics)
1. **Số Lỗi Vi Phạm Ràng Buộc Cứng (Hard Constraint Violations - $C_{\text{hard}}$):**
   $$C_{\text{hard}} = \text{Số slot BLOCK đè lên OCCUPIED} + \text{Số slot BLOCK đè lên SLEEP}$$
   *Mục tiêu chuẩn mực:* Bắt buộc $C_{\text{hard}} = 0$ trên mọi kết quả sinh ra.
2. **Tỷ Lệ Thỏa Mãn Hạn Chót (Deadline Satisfaction Rate - $R_{\text{deadline}}$):**
   $$R_{\text{deadline}} = \frac{\text{Số task được xếp hoàn thành trước hoặc đúng deadline}}{\text{Tổng số task có deadline}} \times 100\%$$
3. **Thời Gian Tính Toán (Execution Latency - $T_{\text{exec}}$):**
   Thời gian chạy thuật toán tính bằng mili-giây (ms), đo lường bằng module `time.perf_counter()`.
   *Mục tiêu thiết kế:* Dưới 2 giây cho tuần 50 task (theo mục tiêu đề ra tại §9.4 của Báo cáo).
4. **Độ Ổn Định Khi Gặp Sự Cố (Schedule Stability - $S_{\text{stability}}$):**
   Đo lường khi có một cuộc hẹn mới chèn vào lịch đã xếp:
   $$S_{\text{stability}} = \frac{\text{Số block không liên quan giữ nguyên vị trí}}{\text{Tổng số block không bị sự kiện mới đè trực tiếp}} \times 100\%$$

---

### 9.2. Phân Tích Hành Vi Của Thuật Toán Baseline Trên 10 Kịch Bản Kiểm Thử (T01 – T10)

| Mã Test | Tên Kịch Bản | Hành Vi Của Baseline Greedy EDF | Hành Vi Của Thuật Toán Vét Cạn (Backtracking) | Điểm Yếu Baseline Bộc Lộ So Với Hệ Thống Đề Xuất |
| :---: | :--- | :--- | :--- | :--- |
| **T01** | 5 task bình thường, thời gian rảnh dồi dào | Xếp được $100\%$ các task; thời gian giải thực tế sẽ được đo đạc. | Tìm ra nghiệm tối ưu ngay lập tức. | Không tối ưu nhịp sinh học (có thể xếp việc nặng vào khung giờ mệt mỏi nếu giờ đó rảnh sớm). |
| **T02** | Nhiều task có deadline trùng nhau | Xếp theo thứ tự: Deadline $\to$ Priority. Task ưu tiên thấp hơn bị đẩy lùi. | Thử các hoán vị để tìm cách xếp trọn vẹn nhất. | Không có cơ chế kích hoạt "Sprint Mode" để cứu vãn các task bị dồn ứ. |
| **T03** | Task lớn (180p) nhưng tuần chỉ có khoảng trống ngắn | Bị đưa vào `UNPLACED` nếu `is_splittable = False`. Nếu bật split, chia đều 90+90p và xếp được. | Trả về thất bại nếu không cho phép chia nhỏ. | Thuật toán cơ bản không biết tự động gợi ý cách phân nhỏ task một cách thông minh theo ngữ cảnh. |
| **T04** | Sự kiện đột xuất 2 tiếng chèn vào lịch | **Xếp lại toàn bộ từ đầu (Full Rebuild):** Làm xáo trộn cả những task không liên quan; độ ổn định thực tế sẽ được đo đạc. | Tương tự, tính lại toàn bộ cây trạng thái. | Bộc lộ rõ nhược điểm thiếu cơ chế sửa chữa cục bộ (Local Repair). |
| **T05** | Task thực tế làm lâu hơn dự tính (+30%) | Không có đệm thời gian (Buffer) nên task sau bị đè giờ hoặc dời lịch dây chuyền. | Bị vỡ kế hoạch thực tế. | Chứng minh giá trị thực tế của Quy luật Tâm lý học 1: Hệ số đệm thời gian ($\times 1.2 / \times 1.35$). |
| **T06** | Tổng khối lượng việc > Tổng thời gian rảnh | Xếp đến khi hết slot rảnh, các task sau cùng bị đưa vào `UNPLACED`. | Báo Infeasible sau khi duyệt hết nhánh. | Không tính toán được lượng thời gian thiếu hụt cụ thể để cảnh báo sớm cho sinh viên. |
| **T07** | Nhập thiếu thông tin (ví dụ quên deadline) | Bị chặn ngay tại tầng tiền xử lý dữ liệu (Input Validation) hoặc tự gán deadline cuối tuần. | Lỗi đầu vào nếu không có giá trị mặc định. | Không có trợ lý thông minh để hội thoại hỏi lại phần dữ liệu bị khuyết. |
| **T08** | Task không rõ mức độ quan trọng | Xếp theo thứ tự danh sách nhập vào (FIFO). | Không ảnh hưởng do chỉ xét tính khả thi. | Thiếu khả năng suy luận ngữ cảnh công việc từ nội dung văn bản. |
| **T09** | 2 sinh viên: 1 người cú đêm, 1 người dậy sớm | **Cả 2 nhận được lịch trình giống hệt nhau** nếu lịch học giống nhau. | Cho kết quả giống hệt nhau. | Hoàn toàn thất bại trong việc cá nhân hóa theo nhịp năng lượng (Circadian Rhythm). |
| **T10** | Task có hạn chót ở tuần tiếp theo | Xếp vào cuối tuần hiện tại nếu còn dư slot rảnh. | Tương tự. | Chưa có cơ chế quản lý đa tuần linh hoạt. |

---
