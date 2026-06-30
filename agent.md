# PROMPT CHO AI AGENT — XÂY DỰNG & CÂN BẰNG GAME "QUADRANT WARS"

> Copy toàn bộ nội dung dưới đây và đưa cho AI coding agent (Claude Code, Cursor, v.v.) để bắt đầu triển khai.

---

## 0. Vai trò của bạn

Bạn là một kỹ sư phần mềm AI, làm việc cùng tôi để xây dựng hoàn chỉnh game **"Quadrant Wars" (Đại chiến góc phần tư)** — đồ án môn Lập trình Hướng đối tượng (OOP) của nhóm 3 sinh viên. Hãy code **toàn bộ tính năng** theo đặc tả dưới đây, đồng thời chủ động **cân bằng (balance) các thông số gameplay** bằng phương pháp mô phỏng/playtest có hệ thống, không chỉ chọn số liệu cảm tính.

**Ràng buộc bắt buộc:**
- Ngôn ngữ: **Python 3**, thư viện đồ họa: **Pygame**.
- Đây là đồ án OOP nên **thiết kế class phải thể hiện rõ tính đóng gói, kế thừa, đa hình** (encapsulation, inheritance, polymorphism). Tránh viết code thủ tục (procedural) dồn hết logic vào 1 file/hàm `main()`.
- Code phải chạy được, có cấu trúc dự án rõ ràng, dễ chấm điểm và dễ thuyết trình (giảng viên sẽ đọc class diagram).

---

## 1. Tổng quan game

- 1 bản đồ duy nhất (1 vùng đất liền) được chia thành **N vùng lãnh thổ màu khác nhau**, N = số người chơi (2–4).
- Mỗi vùng lãnh thổ là "nhà" của đúng 1 người chơi (người thật hoặc bot). Không có vùng trung lập.
- Người chơi điều khiển quân **Hậu** để sinh thêm quân bằng tài nguyên **Food**, rồi điều **Lính** sang tấn công lãnh thổ đối phương theo thời gian thực (không theo lượt).
- Mục tiêu: tiêu diệt Hậu của tất cả màu khác, chiếm toàn bản đồ.

**Lưu ý chuẩn hóa thuật ngữ:** Tài liệu đề xuất gốc dùng lẫn cả hai tên **"Hậu cần"** và **"Đầu bếp"** để chỉ cùng một loại quân (đơn vị kinh tế sinh Food). Trong code, hãy thống nhất dùng **một tên duy nhất** — gợi ý class `Worker` (hoặc `Logistics`) — để tránh nhầm lẫn khi báo cáo.

---

## 2. Đặc tả chi tiết cơ chế (bám sát đề xuất gốc)

### 2.1. Cài đặt trận đấu
- Màn hình chọn trận: chọn số người chơi (2–4 slot), mỗi slot chọn **Người thật** hoặc **Bot**.
- Sau khi xác nhận, bản đồ được chia thành N vùng lãnh thổ liền kề nhau (gợi ý: sinh N điểm seed ngẫu nhiên rồi dùng thuật toán **Voronoi** để chia vùng — đảm bảo các vùng có diện tích tương đối đồng đều và đều giáp biên với ít nhất 1 vùng khác).
- Mỗi vùng được gán 1 màu, đặt 3 đơn vị khởi điểm tại đó: 1 `Queen`, 1 `Worker`, 1 `Soldier`.

### 2.2. Đơn vị quân & vai trò (map sang class OOP gợi ý ở mục 3)
| Đơn vị | Vai trò | Hành vi đặc trưng |
|---|---|---|
| **Hậu (Queen)** | Đầu não, do người chơi điều khiển trực tiếp | Ra lệnh mua quân; **duy nhất** có quyền điều Lính đi tấn công; bị khóa vị trí tại lãnh thổ nhà |
| **Hậu cần / Worker** | Kinh tế | Tự động sinh Food liên tục theo thời gian thực; bị khóa vị trí tại lãnh thổ nhà |
| **Lính (Soldier)** | Chiến đấu | Là đơn vị cơ động **duy nhất**, có thể rời lãnh thổ để tấn công; sức mạnh = số lượng |

### 2.3. Cơ chế mua quân (Food)
- Food sinh ra real-time, không theo lượt: mỗi `Worker` cộng Food mỗi giây (mặc định **+5 Food/giây/Worker** — coi là hằng số có thể tinh chỉnh).
- Mua **Lính**: giá rẻ, cố định, sinh ngay lập tức khi đủ Food.
- Mua **Worker**: giá đắt hơn Lính và **tăng dần theo số lượng Worker hiện có** của lãnh thổ đó (chống spam kinh tế vô hạn). Gợi ý công thức: `cost(n) = base_cost * growth_rate ^ n` với `n` = số Worker hiện có.
- Không cho phép mua khi không đủ Food (không Food âm).

### 2.4. HP của lãnh thổ
- HP của một vùng = **tổng số lượng tất cả đơn vị đang đứng tại đó** (Queen + Worker + Soldier), không phải một thanh máu cố định.

### 2.5. Cơ chế giao tranh — bản cập nhật cuối cùng (đây là bản chính thức cần code, không phải bản sơ bộ ở mục đầu tài liệu gốc)
Khi Lính tấn công tràn sang một lãnh thổ:

1. **Lớp phòng thủ 1 — Lính thủ nhà:** Lính tấn công và Lính thủ nhà triệt tiêu nhau theo tỉ lệ **1:1** (1 Lính tấn công giết 1 Lính thủ, và ngược lại) cho đến khi 1 trong 2 phía hết Lính.
2. **Nếu Lính thủ nhà bị diệt sạch mà Lính tấn công vẫn còn sống sót →** Queen và Worker của lãnh thổ phòng thủ trở thành đơn vị có thể chiến đấu, với **sức chiến đấu quy đổi sang "đơn vị Lính tương đương"**:
   - 1 **Queen** chống đỡ tương đương **4 Lính tấn công** (tỉ lệ 1:4).
   - 1 **Worker** chống đỡ tương đương **2 Lính tấn công** (tỉ lệ 1:2).
   - Lính tấn công sống sót tiếp tục triệt tiêu vào "máu quy đổi" này theo đúng tỉ lệ trên cho đến khi Queen bị hạ hoặc hết Lính tấn công.

   *Ví dụ cụ thể để code đúng:* Lãnh thổ A bị tấn công bởi 10 Lính. Lãnh thổ A có 6 Lính thủ, 1 Worker, 1 Queen.
   - Bước 1: 10 Lính tấn công vs 6 Lính thủ → 6 cặp triệt tiêu lẫn nhau → còn lại **4 Lính tấn công** sống, 0 Lính thủ.
   - Bước 2: 4 Lính tấn công này đánh vào Worker (giá trị 2 "máu Lính") → tốn 2 Lính tấn công để hạ Worker → còn lại **2 Lính tấn công** sống, Worker chết.
   - Bước 3: 2 Lính tấn công còn lại đánh vào Queen (giá trị 4 "máu Lính") → Queen chỉ mất 2/4 "máu", **Queen sống sót**, quân tấn công hết quân → cuộc tấn công **thất bại**, lãnh thổ A giữ nguyên màu, Queen của A sống với "máu" còn 2/4 quy đổi (cần quyết định: máu Queen có hồi lại theo thời gian hay giữ trạng thái bị thương — xem mục 6, đây là 1 điểm cần bạn (AI agent) tự cân bằng và đề xuất, mặc định đơn giản nhất: Queen hồi đầy ngay khi trận tấn công kết thúc, vì tài liệu gốc không đề cập máu tồn lưu).
   - Nếu thay vào đó có 14 Lính tấn công ban đầu thay vì 10: sau bước 3 sẽ còn dư Lính tấn công đủ giết Queen → lãnh thổ đổi màu, số Lính tấn công sống sót còn lại trở thành lực lượng phòng thủ mới của màu kẻ thắng.
3. **Chiếm lãnh thổ:** Ngay khi Queen của lãnh thổ phòng thủ bị hạ, lãnh thổ đổi sang màu phe tấn công; số Lính tấn công còn sống đóng quân tại đó làm lực lượng phòng thủ mới (Worker và Queen mới — cần quyết định: lãnh thổ vừa chiếm có Queen/Worker mới do người tấn công cử sang không, hay phải xây mới? Đề xuất: lãnh thổ vừa chiếm tạm thời **không có Queen/Worker riêng**, vẫn thuộc quyền kiểm soát và Food của Queen gốc bên tấn công cho tới khi người chơi quyết định "định cư" — nếu thấy phức tạp hoá phạm vi đồ án, có thể đơn giản hoá: vì N vùng = N người chơi và không có vùng trung lập, **kết quả chiếm lãnh thổ = đối phương đó bị loại khỏi trận** luôn, vì họ chỉ có duy nhất 1 lãnh thổ chứa Queen → khớp với mục 2.6 "Thất bại" dưới đây. Hãy code theo hướng đơn giản này trừ khi tôi yêu cầu khác.)

### 2.6. Điều kiện thắng/thua
- **Thua:** lãnh thổ chứa Queen của bạn bị chiếm (vì mỗi người chơi chỉ có 1 lãnh thổ duy nhất, đây đồng nghĩa bị loại khỏi trận ngay).
- **Thắng:** là người chơi/bot cuối cùng còn Queen sống sót trên bản đồ.

### 2.7. Thời gian thực
- Vòng lặp game chạy theo delta-time (không phụ thuộc FPS) để Food, di chuyển quân, giao tranh luôn nhất quán giữa các máy.
- Mua quân là tức thời, không cần xếp hàng chờ lượt.

### 2.8. Di chuyển & trấn thủ
- Queen, Worker: khóa cứng tại lãnh thổ nhà, không di chuyển.
- Lính: đơn vị duy nhất di chuyển được, có thời gian hành quân giữa 2 lãnh thổ (đề xuất gốc không nêu rõ — bạn cần đề xuất 1 cơ chế hợp lý, ví dụ: tốc độ hành quân cố định theo khoảng cách giữa 2 vùng, hoặc tối giản hoá thành "tới ngay" nếu phạm vi đồ án eo hẹp — **hãy hỏi tôi nếu muốn xác nhận trước khi code phần này**, mặc định đề xuất: thời gian hành quân tỉ lệ khoảng cách tâm 2 vùng / 1 tốc độ hành quân cố định, hiển thị Lính di chuyển trên bản đồ để tăng tính chiến thuật).

---

## 3. Kiến trúc OOP gợi ý (bắt buộc thể hiện kế thừa + đa hình)

```
Unit (abstract base class)
 ├── Queen        # override: can_command_attack(), recruit_cost rules
 ├── Worker       # override: produce_food(dt), escalating cost
 └── Soldier      # override: combat_power, is_mobile = True

Territory
 - color, owner, polygon/vùng vẽ, list[Unit], food_balance
 - hp (property tính từ tổng quân số)
 - methods: add_unit(), remove_unit(), resolve_incoming_attack(soldiers, attacker)

Player (abstract base class)
 ├── HumanPlayer   # đọc input bàn phím/chuột
 └── BotPlayer     # override decide_action() — xem mục 5

CombatResolver
 - hàm thuần (pure function/class) nhận (attacking_soldiers, defending_territory)
 - trả về kết quả: ai thắng, số quân còn sống, lãnh thổ có đổi màu hay không
 - tách riêng khỏi Territory để dễ viết unit test độc lập

GameManager / Match
 - vòng lặp chính, quản lý danh sách Territory, Player, điều kiện thắng/thua

MapGenerator
 - sinh N vùng Voronoi từ N điểm seed, trả về polygon từng vùng

Renderer (tách biệt hoàn toàn khỏi logic — không để Pygame code lẫn vào Unit/Territory)
```

**Yêu cầu cụ thể:**
- `Unit` là abstract class (dùng `abc.ABC` + `@abstractmethod`), 3 lớp con override hành vi → thể hiện đa hình rõ ràng khi gọi `unit.update(dt)` hay `unit.combat_value`.
- Encapsulation: thuộc tính nội bộ (food, hp, vị trí...) dùng `_private` + `@property`, không truy cập trực tiếp từ ngoài.
- Có thể áp dụng thêm design pattern nếu phù hợp (không bắt buộc nhưng cộng điểm khi báo cáo OOP):
  - **Factory Method** để tạo Unit theo loại.
  - **Strategy Pattern** cho các "tính cách" bot khác nhau (xem mục 5).
  - **State Pattern** cho các trạng thái trận đấu (menu → đang chơi → kết thúc).

---

## 4. Yêu cầu kỹ thuật Pygame

- Cửa sổ cố định (ví dụ 1280x720), giới hạn 60 FPS, dùng `clock.tick(60)` + delta time thực tế cho logic.
- Màn hình chính: chọn số người chơi (2–4) + người/bot mỗi slot → nút Start.
- Màn hình trận đấu:
  - Vẽ bản đồ chia vùng (polygon màu theo chủ sở hữu).
  - Mỗi vùng hiển thị: số Lính, số Food, icon Queen/Worker.
  - UI mua quân: click vào lãnh thổ của mình → hiện nút "Mua Lính" / "Mua Worker" kèm giá hiện tại.
  - Thao tác tấn công: chọn lãnh thổ nguồn → kéo/click lãnh thổ đích → cử Lính sang (cho chọn số lượng Lính cử đi, không nhất thiết cử hết).
- **Đa người chơi cùng 1 máy (local multiplayer) — điểm đề xuất gốc chưa định nghĩa rõ, bạn cần thiết kế sơ đồ điều khiển và xác nhận với tôi trước khi code UI:**
  - Đề xuất: vì giao tranh real-time và tối đa 4 người thật cùng lúc trên 1 bàn phím/chuột là khó kiểm soát mượt, hãy thiết kế theo hướng **mỗi người chơi có vùng phím riêng** (ví dụ Player1 = WASD + Q/E để chọn-mua-tấn công lãnh thổ của mình, Player2 = phím mũi tên + , / ., Player3/4 dùng numpad nếu có) **HOẶC** đơn giản hơn: dùng chuột cho tất cả nhưng chỉ cho phép tương tác với lãnh thổ thuộc quyền sở hữu (không cần phân vùng phím, vì mỗi người chỉ thao tác trên vùng đất của mình, không có tranh giành click) — **đây là phương án khuyến nghị vì đơn giản và đủ dùng**, hãy làm theo phương án này trừ khi tôi nói khác.

---

## 5. Logic Bot AI (đơn giản nhưng hợp lý, không cần machine learning)

Mỗi vòng lặp quyết định (ví dụ mỗi 0.5–1 giây), bot:
1. Tính tỉ lệ Worker/Soldier hiện có → nếu tỉ lệ kinh tế thấp hơn ngưỡng mục tiêu và đủ Food → mua Worker.
2. Nếu dư Food sau khi xét Worker → mua Soldier.
3. Đánh giá lãnh thổ láng giềng yếu nhất (HP quy đổi thấp hơn lực lượng Lính hiện có của bot một khoảng an toàn, ví dụ Lính hiện có > 1.3x HP đối phương) → cử quân tấn công, **để lại đủ Lính phòng thủ nhà** (ví dụ giữ lại tối thiểu bằng HP trung bình các đối thủ còn lại, hoặc % cấu hình).
4. Có thể tạo 2–3 "tính cách" bot khác nhau (Strategy Pattern) để vừa làm đối thủ luyện tập vừa dùng cho việc cân bằng số liệu ở mục 6 (ví dụ: `AggressiveBot` ưu tiên Lính, `EconomicBot` ưu tiên Worker, `BalancedBot` cân đối cả hai).

---

## 6. CÂN BẰNG GAME — yêu cầu bắt buộc, không chỉ đoán số

Đây là phần quan trọng nhất của prompt này. Sau khi code xong cơ chế, hãy:

1. **Tách toàn bộ hằng số gameplay ra 1 file config riêng** (`balance_config.py` hoặc `.json`): Food/giây mỗi Worker, giá Lính, giá gốc + tỉ lệ tăng giá Worker, tỉ lệ quy đổi Queen (1:4)/Worker (1:2), tốc độ hành quân Lính, Food khởi điểm, số quân khởi điểm. Không hard-code số liệu rải rác trong logic.
2. **Viết một script mô phỏng trận đấu chạy headless** (không cần render đồ họa) cho phép chạy hàng trăm/nghìn trận giữa các cấu hình BotPlayer khác nhau (Aggressive vs Economic vs Balanced, 2–4 người mỗi trận) với seed ngẫu nhiên khác nhau.
3. Ghi log & tổng hợp các chỉ số sau mỗi batch mô phỏng:
   - Tỉ lệ thắng của từng "tính cách" bot.
   - Thời gian trung bình một trận (số giây/phút tới khi có người thắng).
   - Có hiện tượng "snowball" quá nhanh không (1 bên chiếm áp đảo trong <30s là dấu hiệu mất cân bằng kinh tế/chiến đấu).
4. **Mục tiêu cân bằng cụ thể cần đạt** (coi đây là tiêu chí dừng tinh chỉnh, có thể thương lượng lại với tôi nếu thấy bất hợp lý khi thực nghiệm):
   - Không có "tính cách" bot nào thắng áp đảo >65% trong các cặp đối đầu 1v1 mô phỏng — nếu có, đó là dấu hiệu 1 chiến thuật (rush Lính hoặc rush kinh tế) đang OP, cần chỉnh giá/tỉ lệ sản xuất.
   - Thời gian trận trung bình rơi vào khoảng 3–8 phút thời gian thực (phù hợp 1 hiệp chơi cùng bạn bè) — nếu mô phỏng ra quá ngắn (rush chết sớm) hoặc quá dài (turtle vô tận, không ai dám đánh), điều chỉnh giá Lính/sản lượng Food/tỉ lệ quy đổi Queen-Worker.
   - Người chơi luôn có khả năng "comeback" ở mức tối thiểu: 1 lãnh thổ chỉ còn Queen (HP quy đổi thấp) vẫn cần ít nhất vài chục giây phòng thủ được trước khi sụp, không sụp ngay lập tức (kiểm tra qua mô phỏng tình huống bị áp đảo quân số 2:1, 3:1).
5. Sau khi tinh chỉnh, **viết lại các hằng số cuối cùng vào file config + ghi chú ngắn lý do chỉnh (changelog cân bằng)** để nhóm có thể trình bày trong báo cáo đồ án (giảng viên thường hỏi "tại sao chọn số liệu này").
6. Lặp lại tinh chỉnh — mô phỏng cho đến khi đạt các mục tiêu trên hoặc báo lại cho tôi nếu có đánh đổi (trade-off) cần tôi quyết định (ví dụ: muốn trận nhanh hơn thì phải chấp nhận rush kinh tế mạnh hơn).

---

## 7. Cấu trúc thư mục đề xuất

```
quadrant_wars/
├── main.py
├── balance_config.py
├── core/
│   ├── unit.py            # Unit, Queen, Worker, Soldier
│   ├── territory.py
│   ├── player.py          # Player, HumanPlayer, BotPlayer + bot strategies
│   ├── combat.py          # CombatResolver
│   └── map_generator.py   # Voronoi map generation
├── game/
│   ├── game_manager.py
│   └── states.py          # menu / playing / game_over (State Pattern)
├── ui/
│   ├── renderer.py
│   └── widgets.py
├── simulation/
│   └── balance_sim.py     # script mô phỏng headless để cân bằng số liệu
├── tests/
│   └── test_combat.py     # unit test cho CombatResolver (đặc biệt case Queen/Worker 1:4, 1:2)
└── assets/
```

---

## 8. Quy trình triển khai từng bước

1. Dựng skeleton class (mục 3) trước, chưa cần render — viết unit test cho `CombatResolver` theo đúng ví dụ số ở mục 2.5 (10 Lính tấn công vs 6+1+1) để chốt logic đúng trước khi vẽ UI.
2. Map generator (Voronoi N vùng) + kiểm tra hiển thị tạm bằng matplotlib hoặc Pygame thô.
3. Game loop real-time: Food tích lũy, mua quân, cập nhật Territory.
4. Cơ chế tấn công + di chuyển Lính + áp dụng CombatResolver khi quân tới đích.
5. Điều kiện thắng/thua + màn hình kết thúc.
6. Bot AI (3 tính cách ở mục 5).
7. UI hoàn chỉnh: menu chọn người chơi, HUD trong trận, hiệu ứng đổi màu lãnh thổ khi bị chiếm.
8. Chạy `simulation/balance_sim.py`, tinh chỉnh `balance_config.py` theo mục 6 cho tới khi đạt mục tiêu cân bằng.
9. Polish: hiệu ứng chuyển động Lính trên bản đồ, âm thanh (tùy chọn), tối ưu FPS.

Sau mỗi bước lớn, dừng lại báo cáo ngắn cho tôi: đã code gì, còn vướng quyết định thiết kế nào cần tôi xác nhận (đặc biệt 2 điểm đã đánh dấu "cần hỏi" ở mục 2.8 và 4), trước khi sang bước kế tiếp.

---

## 9. Tiêu chí hoàn thành (checklist)

- [ ] Class `Unit` abstract + 3 subclass thể hiện đa hình rõ ràng (đọc được trong code review).
- [ ] Menu chọn 2–4 người chơi, mỗi slot Người/Bot.
- [ ] Bản đồ chia N vùng tự động, đều và liền kề.
- [ ] Food tích lũy real-time, mua Lính/Worker đúng công thức giá leo thang.
- [ ] CombatResolver xử lý đúng case: Lính vs Lính 1:1, và case Queen (1:4)/Worker (1:2) khi Lính thủ hết — có unit test chứng minh.
- [ ] Chiếm lãnh thổ đổi màu, quân sống sót trở thành phòng thủ mới.
- [ ] Thắng/thua phát hiện đúng, có màn hình kết thúc.
- [ ] Bot chơi được hợp lý, không đứng yên không hành động, không tự sát vô lý.
- [ ] `balance_config.py` tách riêng toàn bộ số liệu, có changelog cân bằng.
- [ ] `simulation/balance_sim.py` chạy được, có log số liệu tỉ lệ thắng + thời gian trận.
- [ ] Đạt mục tiêu cân bằng ở mục 6 (hoặc báo cáo trade-off còn tồn đọng).

---

## 10. Hai điểm cần xác nhận trước khi code (đừng tự quyết âm thầm)

1. **Thời gian hành quân của Lính** giữa 2 lãnh thổ: tới ngay lập tức, hay mất thời gian theo khoảng cách? (ảnh hưởng lớn tới chiều sâu chiến thuật và độ khó UI vẽ quân di chuyển).
2. **Lãnh thổ vừa chiếm được có cần Queen/Worker mới hay không**, hay đơn giản hoá thành "chiếm Queen = đối thủ bị loại luôn" như đề xuất ở mục 2.5 (khuyến nghị chọn phương án đơn giản để vừa khung thời gian đồ án).

Nếu không có phản hồi, hãy code theo phương án mặc định đã đề xuất trong từng mục và ghi rõ giả định đó trong README để tôi review.
