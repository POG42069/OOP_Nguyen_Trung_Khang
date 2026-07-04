# Quadrant Wars

**Quadrant Wars** là game chiến thuật thời gian thực viết bằng Python 3 và Pygame cho đồ án OOP. Mỗi người chơi sở hữu một vùng lãnh thổ, tích lũy tài nguyên, tuyển quân, điều lính tấn công và cố gắng hạ Queen của các đối thủ.

## Điểm nổi bật

- Hỗ trợ 2-4 người chơi, mỗi slot có thể là `Human` hoặc `Bot`.
- Bot có 3 phong cách: Aggressive, Balanced và Economic.
- Giao tranh diễn ra theo thời gian thực, lính phải hành quân qua bản đồ thay vì gây sát thương tức thời.
- Tài nguyên sinh nhanh hơn, bot ít thủ hơn và đánh sớm hơn để trận có giao tranh từ đầu.
- Combat có attrition rõ ràng: khi lớp lính đã hết, worker/queen có thể bị kết liễu bằng các đợt đánh nhỏ, tránh kẹt ván.
- UI Pygame có menu, sidebar thống kê, battle log, hiệu ứng hành quân và hiệu ứng giao tranh.

## Cài đặt

Yêu cầu Python 3.10+.

```powershell
pip install -r requirements.txt
```

## Chạy game

```powershell
python -m quadrant_wars.main
```

Hoặc:

```powershell
python quadrant_wars\main.py
```

## Hướng dẫn chơi

Trong menu, chọn số lượng người chơi từ 2 đến 4. Bấm từng slot để đổi giữa `Human` và `Bot`, sau đó chọn `Start Match`.

Trong trận:

| Thao tác | Chức năng |
| --- | --- |
| Click lãnh thổ của mình | Chọn nguồn quân |
| Click lãnh thổ địch | Gửi quân từ vùng đang chọn sang tấn công |
| `1` | Mua Soldier cho vùng đang chọn |
| `2` | Mua Worker cho vùng đang chọn |
| `+` / `-` hoặc `Up` / `Down` | Tăng/giảm tỉ lệ quân đem đi |
| `Esc` | Quay lại menu |

Hotkey nhanh cho 4 người chơi Human:

| Player | Chọn nhà chính | Mua Soldier | Mua Worker |
| --- | --- | --- | --- |
| Player 1 | `F1` | `Q` | `A` |
| Player 2 | `F2` | `W` | `S` |
| Player 3 | `F3` | `E` | `D` |
| Player 4 | `F4` | `R` | `F` |

Các hotkey mua quân sẽ thao tác trên vùng gần nhất người chơi đó đã chọn. Nếu chưa chọn vùng nào, game tự dùng nhà chính của player tương ứng.

## Luật chính

- Worker sinh food theo thời gian.
- Food dùng để mua Soldier hoặc Worker.
- Soldier là đơn vị duy nhất có thể rời lãnh thổ để tấn công.
- Queen và Worker ở lại lãnh thổ nhà.
- Khi Queen của một người chơi bị hạ, người chơi đó bị loại.
- Vùng vừa bị chiếm chỉ giữ lại số Soldier sống sót, không tự sinh Queen/Worker mới.

## Cấu trúc OOP

- `quadrant_wars/core/unit.py`: lớp trừu tượng `Unit`, các lớp `Queen`, `Worker`, `Soldier`.
- `quadrant_wars/core/territory.py`: quản lý lãnh thổ, food, unit stack và tuyển quân.
- `quadrant_wars/core/combat.py`: luật combat thuần, tách khỏi UI để dễ test.
- `quadrant_wars/core/player.py`: `Player`, `HumanPlayer`, `BotPlayer` và các strategy bot.
- `quadrant_wars/game/states.py`: state pattern cho menu, playing và game over.
- `quadrant_wars/game/game_manager.py`: vòng đời trận đấu, hành quân, resolve combat và thắng thua.
- `quadrant_wars/ui/renderer.py`: render Pygame, sidebar, map, unit sprite và hiệu ứng.

## Test và mô phỏng cân bằng

```powershell
python -m unittest discover -s quadrant_wars\tests
python quadrant_wars\simulation\balance_sim.py --matches 100 --players 2 3 4
```

Các hằng số gameplay nằm trong `quadrant_wars/balance_config.py` để dễ tinh chỉnh nhịp trận, tốc độ sinh tài nguyên, chi phí quân và hành vi bot.
