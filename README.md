# 科普问答系统 0.2 版本

基于 React+Vite 前端和 FastAPI 后端的科普问答智能体系统，支持流式输出、认知水平评估、手绘意图检测等功能。

## 目录

- [系统架构](#系统架构)
- [后端部署](#后端部署)
- [前端部署](#前端部署)
- [WebSocket API 接口说明](#websocket-api-接口说明)
- [请求 JSON 格式](#请求-json-格式)
- [响应 JSON 格式](#响应-json-格式)
- [状态机说明](#状态机说明)
- [认知水平等级](#认知水平等级)

---

## 系统架构

```
┌─────────────┐       WebSocket        ┌─────────────┐
│   前端       │ ◄────────────────────► │   后端       │
│ React+Vite  │                        │  FastAPI    │
│  (port 5173)│                        │  (port 8000)│
└─────────────┘                        └─────────────┘
                                            │
                                            ▼
                                       ┌─────────────┐
                                       │   LLM API   │
                                       │  (流式输出)  │
                                       └─────────────┘
```

---

## 后端部署

### 环境要求

- Python 3.10+
- pip

### 安装步骤

1. 进入后端目录：
   ```bash
   cd 0.2/backend
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 启动服务：
   ```bash
   python server.py
   ```

   或使用 uvicorn：
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```

### 配置说明

- WebSocket 端点：`ws://localhost:8000/ws`
- 默认端口：`8000`

---

## 前端部署

### 环境要求

- Node.js 16+
- npm

### 安装步骤

1. 进入前端目录：
   ```bash
   cd 0.2/frontend
   ```

2. 安装依赖：
   ```bash
   npm install
   ```

3. 启动开发服务器：
   ```bash
   npm run dev
   ```

4. 打开浏览器访问：`http://localhost:5173`

### 构建生产版本

```bash
npm run build
```

---

## WebSocket API 接口说明

本系统使用 WebSocket 进行前后端通信，所有消息均为 JSON 格式。

### 连接地址

```
ws://localhost:8000/ws
```

### 通信流程

1. 前端建立 WebSocket 连接
2. 用户接近时发送 `has_person_change` 消息（`has_person: true`）
3. 用户输入问题时发送 `has_person_change` 消息（包含 `message` 字段）
4. 用户离开时发送 `has_person_change` 消息（`has_person: false`）
5. 后端通过流式输出返回响应

---

## 请求 JSON 格式

前端（或其他系统）发送给后端的消息格式：

```json
{
  "message_id": "msg_abc123",
  "session_id": "sess_xyz789",
  "timestamp": "2026-05-09T12:00:00+00:00",
  "action": "has_person_change",
  "payload": {
    "has_person": true,
    "age": 14,
    "gender": "female",
    "message": "什么是人工智能？"
  }
}
```

### 外层字段说明

| 字段名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `message_id` | string | 是 | 消息唯一标识，格式为 `msg_` 前缀 + 随机字符串 |
| `session_id` | string | 是 | 会话标识，格式为 `sess_` 前缀 + 随机字符串 |
| `timestamp` | string | 是 | ISO 8601 时间戳 |
| `action` | string | 是 | 动作类型，可选值：`has_person_change`、`user_input`、`user_left` |
| `payload` | object | 是 | 业务数据 |

### payload 字段说明

| 字段名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `has_person` | boolean | 是 | 屏幕前是否有人；有人为 `true`，无人为 `false` |
| `age` | integer/null | 否 | 当前用户年龄，未知为 `null` |
| `gender` | string/null | 否 | 当前用户性别，可选值：`male`、`female`，未知为 `null` |
| `message` | string | 否 | 用户说话内容，无本次话语时为空字符串 |

### 使用示例

**用户接近：**
```json
{
  "message_id": "msg_001",
  "session_id": "sess_001",
  "timestamp": "2026-05-09T12:00:00+00:00",
  "action": "has_person_change",
  "payload": {
    "has_person": true,
    "age": 14,
    "gender": "female",
    "message": ""
  }
}
```

**用户提问：**
```json
{
  "message_id": "msg_002",
  "session_id": "sess_001",
  "timestamp": "2026-05-09T12:01:00+00:00",
  "action": "has_person_change",
  "payload": {
    "has_person": true,
    "age": 14,
    "gender": "female",
    "message": "什么是人工智能？"
  }
}
```

**用户离开：**
```json
{
  "message_id": "msg_003",
  "session_id": "sess_001",
  "timestamp": "2026-05-09T12:05:00+00:00",
  "action": "has_person_change",
  "payload": {
    "has_person": false,
    "age": null,
    "gender": null,
    "message": ""
  }
}
```

---

## 响应 JSON 格式

后端发送给前端（或其他系统）的消息格式：

```json
{
  "message_id": "msg_abc123",
  "session_id": "sess_xyz789",
  "timestamp": "2026-05-09T12:00:01+00:00",
  "payload": {
    "message_text": "人工智能是让机器完成需要智能的任务。",
    "text_over": false,
    "cognitive_level": "level_2",
    "should_print": false
  }
}
```

### 外层字段说明

| 字段名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `message_id` | string | 是 | 对应请求的 message_id |
| `session_id` | string | 是 | 对应请求的 session_id |
| `timestamp` | string | 是 | ISO 8601 时间戳 |
| `payload` | object | 是 | 响应业务数据 |

### payload 字段说明

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `message_text` | string | 聊天回复文本（**增量累积输出**，见下方说明） |
| `text_over` | boolean | 本次流式输出是否结束 |
| `cognitive_level` | string/null | 认知水平评估结果，破冰后返回，可选值见下方表格 |
| `should_print` | boolean/null | 是否需要手绘输出；`true` 表示需要，`false` 表示不需要，`null` 表示未评估 |

### 流式输出说明

后端采用**增量累积输出**方式，每次发送的 `message_text` 是累积的完整文本。

例如，智能体生成"我爱你中国"，分为三个 chunk：

| 序号 | chunk | message_text | text_over |
|------|-------|--------------|-----------|
| 1 | "我" | "我" | false |
| 2 | "爱你" | "我爱你" | false |
| 3 | "中国" | "我爱你中国" | true |

前端无需自行累积文本，直接使用 `message_text` 显示即可。

### 响应示例

**流式输出中：**
```json
{
  "message_id": "msg_001",
  "session_id": "sess_001",
  "timestamp": "2026-05-09T12:00:01+00:00",
  "payload": {
    "message_text": "你好，我是柯爸，",
    "text_over": false,
    "cognitive_level": null,
    "should_print": null
  }
}
```

**流式输出结束：**
```json
{
  "message_id": "msg_001",
  "session_id": "sess_001",
  "timestamp": "2026-05-09T12:00:02+00:00",
  "payload": {
    "message_text": "你好，我是柯爸，欢迎来到科普问答！",
    "text_over": true,
    "cognitive_level": null,
    "should_print": null
  }
}
```

**带认知水平评估：**
```json
{
  "message_id": "msg_002",
  "session_id": "sess_001",
  "timestamp": "2026-05-09T12:01:00+00:00",
  "payload": {
    "message_text": "人工智能是让机器完成需要智能的任务。",
    "text_over": true,
    "cognitive_level": "level_2",
    "should_print": null
  }
}
```

---

## 状态机说明

智能体内部使用状态机管理对话流程：

| 状态 | 值 | 描述 |
|------|-----|------|
| IDLE | `idle` | 等待用户接近 |
| GREETING | `greeting` | 寒暄中 |
| ICEBREAKING_QUESTION | `icebreaking_question` | 破冰（主动提问） |
| ICEBREAKING_NO_QUESTION | `icebreaking_no_question` | 破冰（未主动提问） |
| TRANSITION | `transition` | 引导提问 |
| QA | `qa` | 正式问答 |
| ENDING | `ending` | 结束对话 |
| WAITING_FOR_DRAW | `waiting_for_draw` | 等待手绘回复 |
| CHAT | `chat` | 闲聊中 |

### 状态流转

```
IDLE → GREETING → ICEBREAKING_QUESTION/ICEBREAKING_NO_QUESTION → TRANSITION → QA → ENDING → WAITING_FOR_DRAW → CHAT
```

---

## 认知水平等级

| 等级 | 值 | 描述 |
|------|-----|------|
| Level 0 | `level_0` | 基础知识弱，不了解领域 |
| Level 1 | `level_1` | 有基础知识，不了解领域 |
| Level 2 | `level_2` | 了解领域，不了解当前问题 |
| Level 3 | `level_3` | 精深于本领域 |

---

## 其他系统调用示例

### Python WebSocket 客户端示例

```python
import asyncio
import json
import websockets

async def main():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # 发送用户接近消息
        message = {
            "message_id": "msg_001",
            "session_id": "sess_001",
            "timestamp": "2026-05-09T12:00:00+00:00",
            "action": "has_person_change",
            "payload": {
                "has_person": True,
                "age": 14,
                "gender": "female",
                "message": ""
            }
        }
        await websocket.send(json.dumps(message))

        # 接收流式响应
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            print(data["payload"]["message_text"], end="")
            if data["payload"]["text_over"]:
                print()
                break

asyncio.run(main())
```

### JavaScript WebSocket 客户端示例

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  const message = {
    message_id: 'msg_001',
    session_id: 'sess_001',
    timestamp: new Date().toISOString(),
    action: 'has_person_change',
    payload: {
      has_person: true,
      age: 14,
      gender: 'female',
      message: ''
    }
  };
  ws.send(JSON.stringify(message));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.payload.message_text);
  if (data.payload.text_over) {
    console.log('输出完成');
  }
};
```

---

## 命令行测试后端

如果不使用前端，可以直接通过命令行工具测试后端 WebSocket API。

### 方法一：使用 Python 脚本（推荐）

创建一个测试脚本 `test_backend.py`：

```python
import asyncio
import json
import websockets

async def test_backend():
    uri = "ws://localhost:8000/ws"
    
    async with websockets.connect(uri) as websocket:
        print("=== 已连接到后端 ===")
        
        # 步骤 1: 用户接近
        print("\n[1] 发送用户接近消息...")
        message = {
            "message_id": "msg_001",
            "session_id": "sess_001",
            "timestamp": "2026-05-09T12:00:00+00:00",
            "action": "has_person_change",
            "payload": {
                "has_person": True,
                "age": 14,
                "gender": "female",
                "message": ""
            }
        }
        await websocket.send(json.dumps(message))
        
        # 接收寒暄响应
        print("\n[智能体寒暄]:")
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            text = data["payload"]["message_text"]
            text_over = data["payload"]["text_over"]
            print(text, end="", flush=True)
            if text_over:
                print("\n")
                break
        
        # 步骤 2: 用户提问（破冰问题1）
        print("\n[2] 发送用户问题...")
        message = {
            "message_id": "msg_002",
            "session_id": "sess_001",
            "timestamp": "2026-05-09T12:01:00+00:00",
            "action": "has_person_change",
            "payload": {
                "has_person": True,
                "age": 14,
                "gender": "female",
                "message": "你好，我想了解人工智能"
            }
        }
        await websocket.send(json.dumps(message))
        
        # 接收响应
        print("\n[智能体回复]:")
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            text = data["payload"]["message_text"]
            text_over = data["payload"]["text_over"]
            cognitive_level = data["payload"].get("cognitive_level")
            
            print(text, end="", flush=True)
            if cognitive_level:
                print(f"\n[认知水平]: {cognitive_level}")
            
            if text_over:
                print("\n")
                break
        
        # 步骤 3: 用户离开
        print("\n[3] 发送用户离开消息...")
        message = {
            "message_id": "msg_003",
            "session_id": "sess_001",
            "timestamp": "2026-05-09T12:05:00+00:00",
            "action": "has_person_change",
            "payload": {
                "has_person": False,
                "age": None,
                "gender": None,
                "message": ""
            }
        }
        await websocket.send(json.dumps(message))
        
        # 接收离开响应
        response = await websocket.recv()
        data = json.loads(response)
        print(f"\n[智能体]: {data['payload']['message_text']}")
        
        print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_backend())
```

**运行测试：**
```bash
# 安装 websockets 库
pip install websockets

# 运行测试脚本
python test_backend.py
```

### 方法二：使用 websocat 工具

[websocat](https://github.com/vi/websocat) 是一个命令行 WebSocket 客户端。

**安装 websocat：**
```bash
# Windows (使用 scoop)
scoop install websocat

# 或者从 GitHub 下载二进制文件
# https://github.com/vi/websocat/releases
```

**测试步骤：**

1. 启动 websocat 连接：
```bash
websocat ws://localhost:8000/ws
```

2. 在终端中输入 JSON 消息（每行一条）：

```json
{"message_id":"msg_001","session_id":"sess_001","timestamp":"2026-05-09T12:00:00+00:00","action":"has_person_change","payload":{"has_person":true,"age":14,"gender":"female","message":""}}
```

3. 查看后端返回的 JSON 响应

4. 发送用户问题：
```json
{"message_id":"msg_002","session_id":"sess_001","timestamp":"2026-05-09T12:01:00+00:00","action":"has_person_change","payload":{"has_person":true,"age":14,"gender":"female","message":"什么是人工智能？"}}
```

5. 发送用户离开：
```json
{"message_id":"msg_003","session_id":"sess_001","timestamp":"2026-05-09T12:05:00+00:00","action":"has_person_change","payload":{"has_person":false,"age":null,"gender":null,"message":""}}
```

### 方法三：使用 wscat 工具

[wscat](https://github.com/websockets/wscat) 是 Node.js 的 WebSocket 客户端。

**安装 wscat：**
```bash
npm install -g wscat
```

**测试步骤：**

1. 连接 WebSocket：
```bash
wscat -c ws://localhost:8000/ws
```

2. 输入 JSON 消息进行测试

### 方法四：使用 curl（仅限简单测试）

curl 不支持 WebSocket，但可以使用 `--include` 参数查看握手响应：

```bash
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  ws://localhost:8000/ws
```

### 快速测试脚本（简化版）

如果只需要快速测试后端是否正常工作，可以使用这个简化脚本：

```python
import asyncio
import json
import websockets

async def quick_test():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        # 发送用户接近
        await ws.send(json.dumps({
            "message_id": "msg_001",
            "session_id": "sess_001",
            "timestamp": "2026-05-09T12:00:00+00:00",
            "action": "has_person_change",
            "payload": {"has_person": True, "age": 14, "gender": "male", "message": ""}
        }))
        
        # 接收并打印所有响应
        for _ in range(10):  # 最多接收10条消息
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(resp)
                print(data["payload"]["message_text"], end="")
                if data["payload"]["text_over"]:
                    print("\n--- 消息结束 ---\n")
            except asyncio.TimeoutError:
                break

asyncio.run(quick_test())
```

---

## 常见问题

### Q: 流式输出不工作？
A: 确保 LLM API 配置正确，检查 `llm_api.py` 中的 API 密钥和端点配置。

### Q: 认知水平始终为 null？
A: 认知水平在破冰结束后才会返回，确保完成至少两轮破冰对话。

### Q: 用户离开后状态未重置？
A: 确保发送 `has_person: false` 的消息，后端会自动重置状态。
