# Quadrant Wars

Game đồ án OOP bằng Python 3 + Pygame, triển khai theo mô tả trong `agent.md` và file Word đề xuất.

## Cách chạy

```powershell
pip install -r requirements.txt
python -m quadrant_wars.main
```

Hoặc:

```powershell
python quadrant_wars\main.py
```

## Điều khiển

- Menu: chọn 2-4 slot, bấm từng slot để đổi `Human`/`Bot`, rồi `Start`.
- Trong trận: click lãnh thổ của mình để chọn.
- Bấm `1` để mua Soldier, `2` để mua Worker.
- Bấm `+/-` hoặc mũi tên lên/xuống để đổi tỉ lệ quân đem đi.
- Click lãnh thổ địch sau khi chọn nguồn để tấn công.
- `Esc` quay lại menu.

## Giả định thiết kế

- Lính hành quân theo khoảng cách giữa tâm 2 lãnh thổ, không tới tức thời.
- Queen và Worker bị khóa ở lãnh thổ nhà.
- Khi Queen của một người chơi bị hạ, người chơi đó bị loại. Vùng vừa chiếm không sinh Queen/Worker mới, chỉ có lính sống sót làm quân đồn trú.
- Queen/Worker không giữ máu bị thương sau trận; nếu chưa bị tiêu diệt hoàn toàn thì coi như hồi phục sau giao tranh.

## Cấu trúc OOP

- `core/unit.py`: `Unit` abstract base class, `Queen`, `Worker`, `Soldier` override `update()` và `combat_value`.
- `core/territory.py`: đóng gói food, unit stacks, mua quân, HP và trạng thái lãnh thổ.
- `core/combat.py`: `CombatResolver` tách riêng để unit test.
- `core/player.py`: `Player` abstract, `HumanPlayer`, `BotPlayer`, `BotStrategy` và 3 chiến thuật bot.
- `game/states.py`: State Pattern cho menu, playing, game over.
- `ui/renderer.py`: renderer Pygame tách khỏi logic core.

## Test và mô phỏng cân bằng

```powershell
python -m unittest discover -s quadrant_wars\tests
python quadrant_wars\simulation\balance_sim.py --matches 100 --players 2 3 4
```

`balance_config.py` chứa toàn bộ hằng số gameplay và ghi chú changelog cân bằng.

