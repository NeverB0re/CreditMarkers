# Medal & Super Credit Markers
<img width="1920" height="1200" alt="스크린샷 2026-11-02 153048" src="https://github.com/user-attachments/assets/68bc2010-b465-41bb-8e28-3d9aa048bcbe" />

A **HELLDIVERS 2** mod that marks medals and super credits lying about the map, from far away, with the game's own
currency icons and their distance above them. It runs on **Chef Shared Loader** and works beside other Chef mods,
including Extended Pickup Icons Range.

[한국어 설명은 아래에 있습니다.](#한국어)

## Install

1. Install [Chef Shared Loader](https://www.nexusmods.com/helldivers2/mods/17760) and give it the highest priority in your
   mod manager (in Arsenal, by default, the bottom of the list).
2. Download the ZIP from [Releases](../../releases) and import it into your mod manager (Arsenal etc.).
3. Purge and Deploy, then start the game.

## Settings

Press **F9** in the game (Chef Shared Loader's options menu) and pick **Medal & Super Credit Markers**:

| Setting | Default |
| --- | --- |
| Show medals | on |
| Show super credits | on |
| Distance | 2000 m (a whole map, end to end), measured across the ground from the camera |
| Show distance above markers | on |

## Limits

- The game doesn't tell mods what a thing's state is. A marker goes when the item's unit goes or stops showing anything.
  Whether every item taken goes that way hasn't been checked in play yet: tell me if a marker stays.
- The medal's unit has no name in the game's files. It was identified from its package and its look, and confirmed by
  playing one mission.
- At most the 30 nearest markers are drawn. Items off screen get none.
- After a game update, the medal may stop showing if its unit changes.

## Crashes

The mod makes few engine calls, all through Chef's guards, and stays on after a crash: Chef only skips the call that
crashed. If it happens, `chef_loader_state.txt` and `MedalCreditMarkers.log` in `%APPDATA%\Arrowhead\Helldivers2` tell why.

## Building

Needs Python 3 and, for the tests, `lupa`.

```bash
python -m pip install lupa
python -m unittest discover -s tests
python build.py
```

| Path | What |
| --- | --- |
| `src/medal_credit_markers.lua` | The mod (PUC Lua 5.1). `VERSION` and `TARGETS` are here. |
| `tools/icons/*.svg` | The game's currency icons, extracted with [filediver](https://github.com/xypwn/filediver). |
| `tools/make_icons.py` | Turns them into textures. Run alone: writes `tools/preview.png` and `src/icon.png`. |
| `build.py` | Writes `dist/Medal & Super Credit Markers v<version>.zip`. |
| `tests/` | Runs the mod against a fake Chef Shared Loader. |

See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). This is an unofficial fan mod.

---

## 한국어

맵에 놓인 메달과 슈퍼 크레딧을 게임의 재화 아이콘과 거리 표시로 멀리서 보여 주는 **헬다이버즈 2** 모드입니다.
**Chef Shared Loader**에서 돌아가며, Extended Pickup Icons Range 등 다른 Chef 모드와 함께 쓸 수 있습니다.

### 설치

1. [Chef Shared Loader](https://www.nexusmods.com/helldivers2/mods/17760)를 설치하고 모드 관리자에서 가장 높은 우선순위로 둡니다
   (Arsenal 기본 설정에서는 목록 맨 아래).
2. [Releases](../../releases)에서 ZIP을 받아 모드 관리자(Arsenal 등)에 가져옵니다.
3. Purge 후 Deploy하고 게임을 시작합니다.

### 설정

게임 중 **F9**(Chef Shared Loader 옵션 메뉴)에서 **Medal & Super Credit Markers**를 고릅니다.

| 설정 | 기본값 |
| --- | --- |
| Show medals (메달 표시) | 켜짐 |
| Show super credits (슈퍼 크레딧 표시) | 켜짐 |
| Distance (표시 거리) | 2000m (맵 끝에서 끝까지), 카메라에서 잰 수평 거리 |
| Show distance above markers (거리 표시) | 켜짐 |

### 한계점

- 게임은 물체의 상태를 모드에 알려 주지 않습니다. 유닛이 사라지거나 아무것도 보이지 않게 되면 마커를 지웁니다. 주운 모든 경우에
  그렇게 되는지는 아직 플레이로 확인하지 못했습니다. 마커가 남으면 알려 주세요.
- 메달 유닛은 게임 파일에 이름이 없어서, 패키지와 모양으로 찾은 뒤 임무 한 번을 플레이해 확인했습니다.
- 가까운 순서로 최대 30개까지 표시하고, 화면 밖 물체는 표시하지 않습니다.
- 게임 업데이트로 메달 유닛이 바뀌면 메달이 표시되지 않을 수 있습니다.

### 크래시

엔진 호출을 최소화했고 모두 Chef의 보호를 거치며, 튕겨도 모드가 꺼지지 않고 Chef가 문제 호출만 건너뜁니다. 원인은
`%APPDATA%\Arrowhead\Helldivers2`의 `chef_loader_state.txt`와 `MedalCreditMarkers.log`에서 볼 수 있습니다.
