import asyncio
import json
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from agent import ScienceAgent, AgentState

app = FastAPI()
agent = ScienceAgent()

PREV_HAS_PERSON = None
TIMEOUT_TASK = None
GREETING_TIMEOUT_TASK = None

def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

def make_response(message_id: str, session_id: str, message_text: str, text_over: bool,
                  cognitive_level=None, should_print=None):
    payload = {
        "message_text": message_text,
        "text_over": text_over,
        "cognitive_level": cognitive_level,
        "should_print": should_print
    }
    return {
        "message_id": message_id,
        "session_id": session_id,
        "timestamp": get_timestamp(),
        "payload": payload
    }

def make_error_response(message_id: str, session_id: str, error_msg: str):
    return {
        "message_id": message_id,
        "session_id": session_id,
        "timestamp": get_timestamp(),
        "payload": {
            "message_text": f"错误：{error_msg}",
            "text_over": True,
            "cognitive_level": None,
            "should_print": None
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global PREV_HAS_PERSON, TIMEOUT_TASK, GREETING_TIMEOUT_TASK
    PREV_HAS_PERSON = None
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_id = message.get("message_id", "")
            session_id = message.get("session_id", "")
            action = message.get("action")

            if action == "has_person_change":
                payload = message.get("payload", {})
                has_person = payload.get("has_person")
                age = payload.get("age")
                gender = payload.get("gender")
                user_message = payload.get("message", "")

                if TIMEOUT_TASK and not TIMEOUT_TASK.done():
                    TIMEOUT_TASK.cancel()
                    TIMEOUT_TASK = None
                if GREETING_TIMEOUT_TASK and not GREETING_TIMEOUT_TASK.done():
                    GREETING_TIMEOUT_TASK.cancel()
                    GREETING_TIMEOUT_TASK = None

                responses = await handle_has_person_change(
                    has_person, age, gender, user_message, message_id, session_id, websocket
                )
                for resp in responses:
                    await websocket.send_text(json.dumps(resp, ensure_ascii=False))

                if has_person and agent.state in [
                    AgentState.ICEBREAKING_QUESTION,
                    AgentState.ICEBREAKING_NO_QUESTION, AgentState.TRANSITION,
                    AgentState.QA, AgentState.WAITING_FOR_DRAWING, AgentState.CHAT
                ]:
                    TIMEOUT_TASK = asyncio.create_task(start_user_timeout(websocket, message_id, session_id))

            elif action == "user_input":
                payload = message.get("payload", {})
                user_input = payload.get("message", "")
                responses = await handle_user_input(user_input, message_id, session_id, websocket)
                for resp in responses:
                    await websocket.send_text(json.dumps(resp, ensure_ascii=False))

                if agent.state in [
                    AgentState.ICEBREAKING_QUESTION,
                    AgentState.ICEBREAKING_NO_QUESTION, AgentState.TRANSITION,
                    AgentState.QA, AgentState.WAITING_FOR_DRAWING, AgentState.CHAT
                ]:
                    TIMEOUT_TASK = asyncio.create_task(start_user_timeout(websocket, message_id, session_id))

            elif action == "user_left":
                cleanup_tasks()
                agent.reset()
                PREV_HAS_PERSON = None

    except WebSocketDisconnect:
        cleanup_tasks()
        agent.reset()
        PREV_HAS_PERSON = None
    except Exception as e:
        cleanup_tasks()
        agent.reset()
        PREV_HAS_PERSON = None
        try:
            await websocket.send_text(json.dumps(
                make_error_response("err_001", "sess_001", str(e)), ensure_ascii=False
            ))
        except:
            pass

def cleanup_tasks():
    global TIMEOUT_TASK, GREETING_TIMEOUT_TASK
    if TIMEOUT_TASK and not TIMEOUT_TASK.done():
        TIMEOUT_TASK.cancel()
        TIMEOUT_TASK = None
    if GREETING_TIMEOUT_TASK and not GREETING_TIMEOUT_TASK.done():
        GREETING_TIMEOUT_TASK.cancel()
        GREETING_TIMEOUT_TASK = None

async def send_stream_response(websocket: WebSocket, stream_gen, message_id: str, session_id: str,
                                cognitive_level=None, should_print=None):
    full_text = ""
    for chunk in stream_gen:
        full_text += chunk
        resp = make_response(message_id, session_id, full_text, False, cognitive_level, should_print)
        await websocket.send_text(json.dumps(resp, ensure_ascii=False))

    resp = make_response(message_id, session_id, full_text, True, cognitive_level, should_print)
    await websocket.send_text(json.dumps(resp, ensure_ascii=False))
    return full_text

async def handle_has_person_change(has_person: bool, age, gender, user_message: str,
                                    message_id: str, session_id: str, websocket: WebSocket):
    global PREV_HAS_PERSON, GREETING_TIMEOUT_TASK

    if PREV_HAS_PERSON is None:
        PREV_HAS_PERSON = False

    print(f"\n[State Change] PREV_HAS_PERSON: {PREV_HAS_PERSON} → {has_person}, agent.state: {agent.state.value}")

    responses = []

    if PREV_HAS_PERSON == False and has_person == True:
        print("[Trigger] 用户接近 → 寒暄")
        if age is not None:
            age = str(age)
        if gender is not None:
            gender = str(gender)
        agent.set_user_info(age if age else "", gender if gender else "")
        agent.icebreak_round = 0
        agent.cognitive_level = None
        agent.should_print = None

        stream_gen = await agent.action_greeting()
        full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
        agent._add_to_history("assistant", full_text)

        GREETING_TIMEOUT_TASK = asyncio.create_task(
            start_greeting_timeout(websocket, message_id, session_id)
        )
        PREV_HAS_PERSON = True
        return []

    elif PREV_HAS_PERSON == True and has_person == False:
        print("[Trigger] 用户离开 → 重置")
        cleanup_tasks()
        agent.reset()
        PREV_HAS_PERSON = False
        resp = make_response(message_id, session_id, "[智能体]用户离开，对话结束", True, None, None)
        return [resp]

    elif PREV_HAS_PERSON == True and has_person == True:
        print(f"[Interaction] agent.state={agent.state.value}, icebreak_round={agent.icebreak_round}, question_count={agent.question_count}")
        if agent.state == AgentState.GREETING:
            agent.user_initiated_question = True
            agent.icebreak_round = 1
            stream_gen = await agent.action_icebreak_question(user_message)
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
            agent._add_to_history("user", user_message)
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.ICEBREAKING_QUESTION and agent.icebreak_round == 1:
            agent.icebreak_round = 2
            stream_gen = await agent.action_icebreak_question(user_message)
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
            agent._add_to_history("user", user_message)
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.ICEBREAKING_QUESTION and agent.icebreak_round == 2:
            cognitive_level = await agent.action_get_cognitive_level()
            stream_gen = await agent.action_answer(user_message)
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id, cognitive_level=cognitive_level)
            agent._add_to_history("user", user_message)
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.ICEBREAKING_NO_QUESTION and agent.icebreak_round == 1:
            agent.icebreak_round = 2
            stream_gen = await agent.action_icebreak_no_question(user_message)
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
            agent._add_to_history("user", user_message)
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.ICEBREAKING_NO_QUESTION and agent.icebreak_round == 2:
            stream_gen = await agent.action_transition()
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.TRANSITION:
            cognitive_level = await agent.action_get_cognitive_level()
            stream_gen = await agent.action_answer(user_message)
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id, cognitive_level=cognitive_level)
            agent._add_to_history("user", user_message)
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.QA:
            cl = agent.cognitive_level.value if agent.cognitive_level else None
            if agent.is_qa_interruption:
                agent.is_qa_interruption = False
                stream_gen = await agent.action_check_user_intent(user_message)
                full_text = await send_stream_response(websocket, stream_gen, message_id, session_id, cognitive_level=cl)
                agent._add_to_history("user", user_message)
                agent._add_to_history("assistant", full_text)

                end_keywords = ["手绘", "画图", "带走", "今天聊", "画成一张图"]
                if any(kw in full_text for kw in end_keywords):
                    agent.state = AgentState.WAITING_FOR_DRAWING
                return []
            else:
                stream_gen = await agent.action_answer(user_message)
                full_text = await send_stream_response(websocket, stream_gen, message_id, session_id, cognitive_level=cl)
                agent._add_to_history("user", user_message)
                agent._add_to_history("assistant", full_text)

                if agent.question_count >= 3:
                    ending_stream = await agent.action_ending()
                    ending_text = await send_stream_response(
                        websocket, ending_stream, message_id, session_id,
                        cognitive_level=cl, should_print=None
                    )
                    agent._add_to_history("assistant", ending_text)
                    agent.state = AgentState.WAITING_FOR_DRAWING

                return []

        elif agent.state == AgentState.WAITING_FOR_DRAWING:
            # 先把用户的回复加入历史，让闲聊时有上下文
            agent._add_to_history("user", user_message)
            drawing_intent = await agent.action_check_drawing_intent(user_message)
            cl = agent.cognitive_level.value if agent.cognitive_level else None
            should_print_val = agent.should_print

            stream_gen = await agent.action_chat(user_message)
            full_text = await send_stream_response(
                websocket, stream_gen, message_id, session_id,
                cognitive_level=cl, should_print=should_print_val
            )
            agent._add_to_history("assistant", full_text)
            return []

        elif agent.state == AgentState.CHAT:
            cl = agent.cognitive_level.value if agent.cognitive_level else None
            stream_gen = await agent.action_chat(user_message)
            full_text = await send_stream_response(websocket, stream_gen, message_id, session_id, cognitive_level=cl)
            agent._add_to_history("user", user_message)
            agent._add_to_history("assistant", full_text)
            return []

    PREV_HAS_PERSON = has_person
    print(f"[End] PREV_HAS_PERSON 更新为: {PREV_HAS_PERSON}")
    return []

async def handle_user_input(user_input: str, message_id: str, session_id: str, websocket: WebSocket):
    return []

async def start_greeting_timeout(websocket: WebSocket, message_id: str, session_id: str):
    await asyncio.sleep(60)
    print("[Timeout] 寒暄超时 → 被动提问")
    if agent.state == AgentState.GREETING and not agent.user_initiated_question:
        agent.icebreak_round = 1
        stream_gen = await agent.action_icebreak_no_question("")
        full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
        agent._add_to_history("assistant", full_text)

async def start_user_timeout(websocket: WebSocket, message_id: str, session_id: str):
    await asyncio.sleep(60)
    print(f"[Timeout] 用户无响应 → agent.state={agent.state.value}")
    if agent.state in [AgentState.GREETING, AgentState.ICEBREAKING_QUESTION, AgentState.ICEBREAKING_NO_QUESTION]:
        stream_gen = await agent.action_interruption_icebreak()
        full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
        agent._add_to_history("assistant", full_text)
    elif agent.state in [AgentState.TRANSITION, AgentState.QA, AgentState.WAITING_FOR_DRAWING, AgentState.CHAT]:
        if agent.state == AgentState.QA:
            agent.is_qa_interruption = True
        elif agent.state in [AgentState.WAITING_FOR_DRAWING, AgentState.CHAT]:
            cleanup_tasks()
            agent.reset()
            global PREV_HAS_PERSON
            PREV_HAS_PERSON = None
            resp = make_response(message_id, session_id, "[智能体]用户离开，对话结束", True, None, None)
            await websocket.send_text(json.dumps(resp, ensure_ascii=False))
            return
        stream_gen = await agent.action_interruption_qa()
        full_text = await send_stream_response(websocket, stream_gen, message_id, session_id)
        agent._add_to_history("assistant", full_text)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
