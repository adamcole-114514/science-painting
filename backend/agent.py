import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, List, Dict
from enum import Enum
from llm_api import call_llm_api

SYSTEM_PROMPT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "system_prompt.txt")

def load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


class AgentState(Enum):
    IDLE = "idle"
    GREETING = "greeting"
    ICEBREAKING_QUESTION = "icebreaking_question"
    ICEBREAKING_NO_QUESTION = "icebreaking_no_question"
    TRANSITION = "transition"
    QA = "qa"
    ENDING = "ending"
    WAITING_FOR_DRAWING = "waiting_for_draw"
    CHAT = "chat"


class CognitiveLevel(Enum):
    LEVEL_0 = "level_0"
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"


class ScienceAgent:
    def __init__(self):
        self.state = AgentState.IDLE
        self.user_info = {}
        self.conversation_history: List[Dict[str, str]] = []
        self.question_count = 0
        self.user_initiated_question = False
        self.system_prompt = load_system_prompt()
        self.icebreak_round = 0
        self.is_qa_interruption = False
        self.cognitive_level: Optional[CognitiveLevel] = None
        self.should_print: Optional[bool] = None

    def reset(self):
        self.state = AgentState.IDLE
        self.user_info = {}
        self.conversation_history = []
        self.question_count = 0
        self.user_initiated_question = False
        self.system_prompt = load_system_prompt()
        self.icebreak_round = 0
        self.is_qa_interruption = False
        self.cognitive_level = None
        self.should_print = None

    def set_user_info(self, age: str, gender: str):
        if not self.user_info:
            self.user_info = {"age": age, "gender": gender}

    def get_user_info_str(self) -> str:
        gender_map = {"male": "男", "female": "女"}
        age = self.user_info.get("age", "")
        gender_raw = self.user_info.get("gender", "")
        gender = gender_map.get(gender_raw, gender_raw)
        if age and gender:
            return f"{gender}，{age}岁"
        elif gender:
            return gender
        elif age:
            return f"{age}岁"
        return "用户"

    def _call_llm_stream(self, user_input: str):
        return call_llm_api(
            system_prompt=self.system_prompt,
            user_input=user_input,
            stream=True,
            conversation_history=self.conversation_history[-8:] if self.conversation_history else None
        )

    def _call_llm(self, user_input: str) -> str:
        response = call_llm_api(
            system_prompt=self.system_prompt,
            user_input=user_input,
            stream=False,
            conversation_history=self.conversation_history[-8:] if self.conversation_history else None
        )
        return response if isinstance(response, str) else "".join(list(response))

    def _add_to_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def _evaluate_cognitive_level(self) -> str:
        conversation_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.conversation_history])
        user_info = self.get_user_info_str()
        prompt = f"""[动作]破冰阶段结束，已获得用户对话信息；[指示]根据以下对话记录和用户基本信息，判断用户的认知水平等级，只需回复等级编号（level_0、level_1、level_2或level_3），不要输出其他内容。

认知等级定义：
level_0：基础知识弱、对领域不了解（例如小学初中生数学基础薄弱且不了解AI领域原理）
level_1：有基础知识、对领域不了解（例如高中、非本专业大学和研究生有数学基础但是不了解AI领域原理）
level_2：有基础知识、了解领域知识、不了解自己提出问题的相关知识（例如对本领域有了解的高中、大学、研究生，但对自己所问问题涉及的知识不了解）
level_3：有基础知识、了解领域知识、精深自己提出问题的相关知识（精深于本领域的高中、大学、研究生、博士和其他科研人员）

用户基本信息：{user_info}
对话记录：{conversation_str}

请回复认知等级："""
        result = self._call_llm(prompt)
        result = result.strip()
        if result.startswith("level_"):
            return result
        for level in ["level_3", "level_2", "level_1", "level_0"]:
            if level in result:
                return level
        return "level_1"

    async def action_greeting(self):
        self.state = AgentState.GREETING
        user_input = "[动作]有用户过来，似乎对这边有兴趣；[指示]主动和用户寒暄，问一下用户有什么想问的。"
        return self._call_llm_stream(user_input)

    async def action_icebreak_question(self, user_response: str):
        self.state = AgentState.ICEBREAKING_QUESTION
        user_info_str = self.get_user_info_str()
        if self.icebreak_round == 1:
            user_input = f"[动作]{user_info_str}，而且立即主动提出了自己的问题；[指示]主动了解用户对计算机和AI领域的了解程度。"
        else:
            user_input = f"[动作]用户说：{user_response}；[指示]如果用户了解该领域，就问一下他是否了解他问的这个问题的原理和知识，想知道的深一些还是浅一些，如果用户不了解该领域，就结合用户信息问问他数学这类的基础知识学的怎么样。"
        return self._call_llm_stream(user_input)

    async def action_icebreak_no_question(self, user_response: str):
        self.state = AgentState.ICEBREAKING_NO_QUESTION
        user_info_str = self.get_user_info_str()
        if self.icebreak_round == 1:
            user_input = f"[动作]{user_info_str}，没有主动提问，只是看着；[指示]主动考察一下用户对计算机和AI领域的了解程度，例如之前学没学过计算机和ai相关知识等问题。"
        else:
            user_input = f"[动作]用户说：{user_response}；[指示]如果用户熟悉该领域的原理和相关知识，则直接询问用户有什么想了解的，如果用户不熟悉该领域，就结合用户信息问问他数学这类的基础知识学的咋样。"
        return self._call_llm_stream(user_input)

    async def action_transition(self):
        self.state = AgentState.TRANSITION
        user_input = "[动作]破冰结束；[指示]由于用户还没提出自己的问题，所以请引导用户提问。"
        return self._call_llm_stream(user_input)

    async def action_answer(self, user_input: str):
        self.state = AgentState.QA
        self.question_count += 1
        conversation_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.conversation_history])
        action_input = f"[动作]用户说：{user_input}；[指示]以之前的对话为基础，根据用户的信息和认知情况进行符合其知识水平的科普，对话记录为：{conversation_str}。"
        return self._call_llm_stream(action_input)

    async def action_ending(self):
        self.state = AgentState.ENDING
        user_input = "[动作]用户聊的时间有点长了；[指示]和用户说一下自己可以通过手绘的方式把今天聊的问题画成一张图让他带走，看看他需不需要。"
        return self._call_llm_stream(user_input)

    async def action_interruption_icebreak(self):
        user_input = "[动作]用户很久没说话；[指示]问问用户是不是自己说的不清楚，还需要再问一遍吗。"
        return self._call_llm_stream(user_input)

    async def action_interruption_qa(self):
        user_input = "[动作]用户很久没说话；[指示]问问用户还有什么想问的吗，引导其提问或者问问他想不想知道他提出的问题的相关内容。"
        return self._call_llm_stream(user_input)

    async def action_check_user_intent(self, user_response: str):
        user_input = f"[动作]用户说：{user_response}；[指示]根据用户的回复，判断用户是否还有想问的问题。如果用户表示不想再问了、没有问题了、要离开了等意思，就询问一下用户是否需要手绘（例如可以说自己可以通过手绘的方式把今天聊的问题画成一张图让他带走）。如果用户还有问题想问，就继续回答用户的问题。"
        return self._call_llm_stream(user_input)

    async def action_check_drawing_intent(self, user_response: str):
        user_input = f"[动作]用户说：{user_response}；[指示]根据用户的回复，判断用户是否需要手绘。只需要回复'需要手绘'或'不需要手绘'即可。"
        response = self._call_llm(user_input)
        self._add_to_history("assistant", response)
        if "需要手绘" in response:
            self.should_print = True
        else:
            self.should_print = False
        return self.should_print

    async def action_chat(self, user_input: str):
        self.state = AgentState.CHAT
        conversation_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.conversation_history])
        action_input = f"[动作]用户说：{user_input}；[指示]继续与用户进行轻松的闲聊，可以聊一些与之前话题相关的延伸内容，或者聊聊科学相关的趣事，对话记录为：{conversation_str}。"
        return self._call_llm_stream(action_input)

    async def action_get_cognitive_level(self):
        level_str = self._evaluate_cognitive_level()
        self.cognitive_level = CognitiveLevel(level_str)
        return self.cognitive_level.value
