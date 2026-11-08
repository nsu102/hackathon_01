# Apple Watch → 서버 → Study Signal

Watch 쪽 앱/수집 경로는 별도입니다. 수집한 측정값을 서버로 보내고, 이 앱은 최신값을 2초 간격으로 읽습니다. 서버에서 값을 보내주는 속도나 Watch 측정 주기를 이 코드가 보장하지 않습니다.

## 기존 서버가 제공할 응답

`GET /heart-rate/latest`에 다음 JSON을 반환하세요. 전송 헤더는 `Authorization: Bearer <STUDY_HEART_TOKEN>`입니다.

```json
{
  "bpm": 72,
  "timestamp": "2026-11-07T12:00:00+00:00",
  "source": "apple_watch",
  "sample_id": "고유한-측정-ID"
}
```

- 필드는 정확히 이 4개입니다. `timestamp`는 반드시 **실제 측정 시각**으로 시간대를 포함해야 합니다. 위 날짜를 재사용하지 마세요.
- `bpm`: 유한한 숫자, 20–250. 숫자 문자열/불리언은 거절합니다.
- `source`: 실제 Watch는 `apple_watch`, 합성 테스트는 `demo`. 데모는 앱에서 구분합니다.
- `sample_id`: 1–128자. 재전송은 같은 ID를 사용합니다. 읽을 때마다 새 시각이나 ID를 만들어 오래된 측정을 새 데이터처럼 보이게 하지 마세요.
- 측정 전에는 `{"status":"waiting"}`을 반환할 수 있습니다.
- 앱은 미래 10초 초과 또는 60초 초과 과거 샘플을 거절합니다. 수신한 값도 측정 후 20초가 지나면 숫자를 숨깁니다. 반복 폴링은 유효 시간을 연장하지 않습니다.
- 원격 주소는 HTTPS를 요구합니다. 로컬 개발은 `http://127.0.0.1` 또는 `http://localhost`를 허용합니다. 쿼리 문자열에 토큰을 넣지 않습니다. 리다이렉트를 따라가지 않습니다.

`.env`:

```dotenv
STUDY_HEART_URL=https://YOUR-COLLECTOR/heart-rate/latest
STUDY_HEART_TOKEN=별도의_읽기_전용_토큰
```

설정 후 앱을 다시 실행하고 ‘서버 연결’을 누르세요. 실패 시 값을 만들어 채우지 않습니다.

## 포함된 개발 릴레이

프로젝트 `.env`의 `HEART_INGEST_TOKEN`, `HEART_READ_TOKEN`에 **서로 다른 24자 이상 랜덤 값**을 설정하세요. 읽기 토큰을 `STUDY_HEART_TOKEN`에도 넣습니다. Watch 업로더에는 ingest 토큰만 전달합니다.

```sh
python3 -m last_hour heart-relay --host 127.0.0.1 --port 8787
```

| 요청 | 토큰 | 동작 |
|---|---|---|
| POST `/heart-rate` | HEART_INGEST_TOKEN | JSON 측정 업로드 |
| GET `/heart-rate/latest` | HEART_READ_TOKEN | 최신 측정 읽기 |

응답은 `{"accepted":true}`이며 같은 ID 재전송은 `{"accepted":false,"reason":"duplicate"}`입니다. 이전 시각의 새 ID 샘플은 거절합니다. 최신 한 값을 메모리에만 유지하고 재시작하면 사라집니다. 요청 본문과 토큰을 로그에 출력하지 않습니다. 브라우저 Origin이 있는 요청은 거절합니다.

외부 수집 서비스로 사용할 때는 별도 서버에 배포하고 HTTPS reverse proxy·기기별 인증·접근 제어를 구성해야 합니다. 현재 개발 릴레이는 단일 사용자용 메모리 프로토타입입니다. 서버 배포와 실제 Watch 전송은 아직 수행하지 않았습니다.
