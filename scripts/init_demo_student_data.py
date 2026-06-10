from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


DEMO_USERNAME = "student_demo"
DEMO_PASSWORD = "StudentDemo2026!"
DEMO_EMAIL = "student_demo@example.local"
DEMO_COURSE_CODE = "DS-DEMO"


def demo_course_payload() -> dict[str, str]:
    return {
        "title": "数据结构演示课",
        "course_code": DEMO_COURSE_CODE,
        "description": "用于比赛演示的学生侧完整学习闭环数据。",
        "subject": "计算机科学",
        "visibility": "private",
        "status": "active",
    }


def build_demo_blueprint() -> dict[str, Any]:
    """Return deterministic demo content shared by the script and tests."""

    return {
        "knowledge_points": [
            {
                "key": "linear-list",
                "name": "线性表",
                "chapter": "第2章 线性表",
                "description": "顺序表、链表及其插入删除操作。",
                "difficulty": "medium",
                "importance": "high",
            },
            {
                "key": "stack-queue",
                "name": "栈与队列",
                "chapter": "第3章 栈与队列",
                "description": "后进先出和先进先出的受限线性结构。",
                "difficulty": "medium",
                "importance": "high",
            },
            {
                "key": "binary-tree",
                "name": "二叉树遍历",
                "chapter": "第5章 树与二叉树",
                "description": "先序、中序、后序与层序遍历。",
                "difficulty": "hard",
                "importance": "high",
            },
        ],
        "wiki_pages": [
            {
                "key": "linear-list",
                "title": "线性表学习 Wiki",
                "slug": "demo-linear-list",
                "summary": "线性表的结构、操作复杂度和常见误区。",
                "content": (
                    "# 线性表\n\n"
                    "线性表是由同类型数据元素构成的有限序列。顺序表适合随机访问，"
                    "链表更适合频繁插入删除。\n\n"
                    "## 来源说明\n\n"
                    "演示种子内容，比赛演示时建议结合公共《数据结构》知识库核对。"
                ),
            },
            {
                "key": "stack-queue",
                "title": "栈与队列对比 Wiki",
                "slug": "demo-stack-queue",
                "summary": "栈与队列的操作限制、应用场景和易混点。",
                "content": (
                    "# 栈与队列\n\n"
                    "栈遵循 LIFO，队列遵循 FIFO。括号匹配、递归调用栈、广度优先搜索"
                    "分别是典型应用。\n\n"
                    "## 易错提醒\n\n"
                    "不要把循环队列的队满条件和队空条件混淆。"
                ),
            },
        ],
        "resources": [
            {
                "resource_type": "explanation",
                "title": "链表插入删除讲解",
                "knowledge_key": "linear-list",
                "content": "## 核心讲解\n链表插入只需改动相邻指针，时间复杂度取决于定位节点。",
                "reason": "根据画像中“喜欢代码示例”的偏好生成。",
            },
            {
                "resource_type": "mindmap",
                "title": "栈与队列思维导图",
                "knowledge_key": "stack-queue",
                "content": "mindmap\n  root(栈与队列)\n    栈\n      LIFO\n      括号匹配\n    队列\n      FIFO\n      BFS",
                "reason": "用于展示 Mermaid 思维导图资源。",
            },
            {
                "resource_type": "diagram",
                "title": "循环队列判空判满流程图",
                "knowledge_key": "stack-queue",
                "content": "flowchart TD\n  A[开始] --> B{front == rear?}\n  B -->|是| C[队空]\n  B -->|否| D{(rear + 1) % n == front?}\n  D -->|是| E[队满]\n  D -->|否| F[可入队或出队]",
                "reason": "用于展示图解说明资源。",
            },
            {
                "resource_type": "flashcard",
                "title": "二叉树遍历闪卡",
                "knowledge_key": "binary-tree",
                "content": "- Q: 中序遍历顺序是什么？\n- A: 左子树、根节点、右子树。",
                "reason": "针对二叉树遍历薄弱点生成。",
            },
        ],
        "quiz_questions": [
            {
                "question_type": "single_choice",
                "knowledge_key": "linear-list",
                "question_text": "顺序表最擅长的操作是？",
                "options": ["随机访问", "任意位置插入", "频繁删除", "动态扩容"],
                "standard_answer": "随机访问",
                "analysis": "顺序表用连续存储，可通过下标 O(1) 访问。",
                "answer_text": "随机访问",
                "is_correct": True,
                "score": Decimal("100.00"),
            },
            {
                "question_type": "multiple_choice",
                "knowledge_key": "stack-queue",
                "question_text": "下列哪些场景常使用栈？",
                "options": ["括号匹配", "函数调用", "BFS", "表达式求值"],
                "standard_answer": "括号匹配;函数调用;表达式求值",
                "analysis": "BFS 通常使用队列，其余三项常用栈。",
                "answer_text": "括号匹配;函数调用",
                "is_correct": False,
                "score": Decimal("70.00"),
            },
            {
                "question_type": "true_false",
                "knowledge_key": "stack-queue",
                "question_text": "队列是一种后进先出的线性结构。",
                "options": [],
                "standard_answer": "错误",
                "analysis": "队列是先进先出，栈才是后进先出。",
                "answer_text": "正确",
                "is_correct": False,
                "score": Decimal("0.00"),
            },
            {
                "question_type": "fill_blank",
                "knowledge_key": "binary-tree",
                "question_text": "中序遍历的访问顺序是左子树、____、右子树。",
                "options": [],
                "standard_answer": "根节点",
                "analysis": "中序遍历按左、根、右访问。",
                "answer_text": "根节点",
                "is_correct": True,
                "score": Decimal("100.00"),
            },
            {
                "question_type": "short_answer",
                "knowledge_key": "linear-list",
                "question_text": "简述链表相比顺序表的一个优势。",
                "options": [],
                "standard_answer": "插入删除时无需整体移动元素。",
                "analysis": "链表通过修改指针完成插入删除，但定位节点仍可能需要 O(n)。",
                "answer_text": "插入删除更方便。",
                "is_correct": True,
                "score": Decimal("85.00"),
            },
            {
                "question_type": "coding",
                "knowledge_key": "stack-queue",
                "question_text": "用栈思想描述括号匹配算法。",
                "options": [],
                "standard_answer": "遇到左括号入栈，遇到右括号检查栈顶是否匹配，最后栈为空则合法。",
                "analysis": "核心是栈顶元素与当前右括号配对。",
                "answer_text": "左括号入栈，右括号弹出。",
                "is_correct": True,
                "score": Decimal("80.00"),
            },
        ],
        "learning_events": [
            "wiki_read",
            "tutor_ask",
            "quiz_start",
            "quiz_complete",
            "profile_updated",
            "diagnosis_generated",
            "recommendation_view",
        ],
    }


async def ensure_demo_student_data(
    *,
    username: str = DEMO_USERNAME,
    password: str = DEMO_PASSWORD,
    email: str = DEMO_EMAIL,
    rebuild: bool = True,
) -> dict[str, Any]:
    from sqlalchemy import delete, select

    from app.core.security import hash_password
    from app.db.session import AsyncSessionLocal
    from app.models.agent import AgentRun
    from app.models.agent_conversation import AgentConversation, AgentMessage, AgentTaskEvent
    from app.models.agent_task import AgentTask, AgentTaskStep
    from app.models.course import Course
    from app.models.diagnosis import DiagnosisReport
    from app.models.evolution import EvolutionEvent, EvolutionStrategy
    from app.models.knowledge import KnowledgePoint
    from app.models.learning_path import LearningPath, LearningPathItem
    from app.models.learning_record import LearningRecord
    from app.models.memory import StudentMemory
    from app.models.profile import LearningPreference, StudentProfile
    from app.models.quiz import AnswerRecord, MistakeBook, Question, Quiz
    from app.models.recommendation import Recommendation
    from app.models.resource import GeneratedResource
    from app.models.user import User
    from app.models.wiki import WikiLink, WikiPage, WikiPageVersion, WikiSource

    blueprint = build_demo_blueprint()
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as db:
        if rebuild:
            await db.execute(delete(User).where(User.username == username))
            await db.commit()

        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role="student",
                status="active",
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)
        else:
            user.email = email
            user.password_hash = hash_password(password)
            user.status = "active"
            user.role = "student"
            old_course = (
                await db.execute(
                    select(Course).where(
                        Course.owner_id == user.id,
                        Course.course_code == DEMO_COURSE_CODE,
                    )
                )
            ).scalar_one_or_none()
            if old_course is not None:
                await db.delete(old_course)
                await db.flush()

        course_payload = demo_course_payload()
        course = Course(owner_id=user.id, **course_payload)
        db.add(course)
        await db.flush()
        await db.refresh(course)

        knowledge_by_key: dict[str, KnowledgePoint] = {}
        for index, item in enumerate(blueprint["knowledge_points"], start=1):
            point = KnowledgePoint(
                course_id=course.id,
                owner_id=user.id,
                scope="personal",
                name=item["name"],
                chapter=item["chapter"],
                description=item["description"],
                difficulty=item["difficulty"],
                importance=item["importance"],
                sort_order=index,
                extra_meta={"demo_key": item["key"], "source": "init_demo_student_data"},
            )
            db.add(point)
            knowledge_by_key[item["key"]] = point
        await db.flush()

        wiki_by_key: dict[str, WikiPage] = {}
        for page_data in blueprint["wiki_pages"]:
            page = WikiPage(
                course_id=course.id,
                owner_id=user.id,
                title=page_data["title"],
                slug=page_data["slug"],
                summary=page_data["summary"],
                content=page_data["content"],
                status="active",
                current_version=1,
                extra_meta={"demo": True, "knowledge_key": page_data["key"]},
            )
            source_point = knowledge_by_key[page_data["key"]]
            page.knowledge_id = source_point.id
            db.add(page)
            await db.flush()
            db.add(
                WikiPageVersion(
                    page_id=page.id,
                    version_number=1,
                    title=page.title,
                    content=page.content,
                    summary=page.summary,
                    change_message="演示数据初始化",
                    created_by=user.id,
                )
            )
            db.add(
                WikiSource(
                    page_id=page.id,
                    source_type="manual",
                    source_id=source_point.id,
                    source_title=source_point.name,
                    quote_text=page.summary,
                    extra_meta={"demo": True},
                )
            )
            wiki_by_key[page_data["key"]] = page

        if {"linear-list", "stack-queue"}.issubset(wiki_by_key):
            db.add(
                WikiLink(
                    source_page_id=wiki_by_key["linear-list"].id,
                    target_page_id=wiki_by_key["stack-queue"].id,
                    relation_type="next",
                    extra_meta={"reason": "线性表之后学习受限线性结构"},
                )
            )

        resources: list[GeneratedResource] = []
        for item in blueprint["resources"]:
            knowledge = knowledge_by_key[item["knowledge_key"]]
            page = wiki_by_key.get(item["knowledge_key"])
            resource = GeneratedResource(
                user_id=user.id,
                course_id=course.id,
                knowledge_id=knowledge.id,
                wiki_page_id=page.id if page else None,
                resource_type=item["resource_type"],
                title=item["title"],
                content=item["content"],
                citations=[
                    {
                        "source_type": "manual",
                        "source_id": str(knowledge.id),
                        "title": knowledge.name,
                        "quote": knowledge.description,
                    }
                ],
                personalized_reason=item["reason"],
                model_name="demo-seed",
                status="active",
            )
            db.add(resource)
            resources.append(resource)

        profile = StudentProfile(
            user_id=user.id,
            major="软件工程",
            grade="大二",
            learning_goal="在两周内补齐数据结构薄弱点，能够独立完成课程实验。",
            profile_summary="偏好代码示例和分步骤讲解，当前对队列判空判满和二叉树遍历较薄弱。",
            mastery_snapshot={"linear-list": 0.78, "stack-queue": 0.52, "binary-tree": 0.48},
            weak_points=["循环队列判空判满", "二叉树递归遍历", "多选题漏选"],
            error_patterns=["概念相近时容易混淆", "代码边界条件检查不足"],
            strategy_summary={
                "dialogue_profile": {
                    "major": "软件工程",
                    "grade": "大二",
                    "learning_preferences": ["Python 代码示例", "分步骤讲解", "短总结"],
                    "evidence": ["来自演示对话初始化"],
                }
            },
            version_no=2,
        )
        db.add(profile)
        db.add(
            LearningPreference(
                user_id=user.id,
                course_id=course.id,
                answer_length="medium",
                explanation_style="code_first",
                resource_preferences=["mindmap", "diagram", "quiz"],
                prompt_params={"tone": "鼓励式", "examples": "Python"},
                confidence=Decimal("0.8600"),
                version_no=2,
            )
        )

        for content, memory_type in [
            ("学生更容易理解带 Python 代码和流程图的解释。", "preference"),
            ("循环队列和二叉树遍历是近期复习重点。", "weakness"),
        ]:
            db.add(
                StudentMemory(
                    user_id=user.id,
                    course_id=course.id,
                    memory_type=memory_type,
                    content=content,
                    evidence=[{"source": "demo_seed", "created_at": now.isoformat()}],
                    confidence=Decimal("0.8200"),
                )
            )

        quiz = Quiz(
            user_id=user.id,
            course_id=course.id,
            knowledge_id=knowledge_by_key["stack-queue"].id,
            title="数据结构多题型演示练习",
            quiz_type="mixed",
            difficulty="medium",
            status="completed",
        )
        db.add(quiz)
        await db.flush()

        first_wrong_answer: AnswerRecord | None = None
        for item in blueprint["quiz_questions"]:
            knowledge = knowledge_by_key[item["knowledge_key"]]
            question = Question(
                quiz_id=quiz.id,
                course_id=course.id,
                knowledge_id=knowledge.id,
                question_type=item["question_type"],
                difficulty="medium",
                question_text=item["question_text"],
                options=item["options"],
                standard_answer=item["standard_answer"],
                analysis=item["analysis"],
                error_tags=["demo", item["knowledge_key"]],
                created_by="ai",
            )
            db.add(question)
            await db.flush()
            answer = AnswerRecord(
                user_id=user.id,
                quiz_id=quiz.id,
                question_id=question.id,
                answer_text=item["answer_text"],
                is_correct=item["is_correct"],
                score=item["score"],
                feedback=item["analysis"],
                error_tags=[] if item["is_correct"] else ["concept_confusion"],
                reviewed_at=now,
            )
            db.add(answer)
            await db.flush()
            if not item["is_correct"] and first_wrong_answer is None:
                first_wrong_answer = answer
                db.add(
                    MistakeBook(
                        user_id=user.id,
                        course_id=course.id,
                        knowledge_id=knowledge.id,
                        question_id=question.id,
                        answer_record_id=answer.id,
                        error_summary="把队列和栈的操作规则混淆，或多选漏选。",
                        correction="复习 FIFO/LIFO 对比，并用流程图检查条件。",
                        error_tags=["concept_confusion", "demo"],
                        status="unresolved",
                    )
                )

        agent_run = AgentRun(
            user_id=user.id,
            course_id=course.id,
            task_type="demo_initialization",
            agent_name="OrchestratorAgent",
            input_payload={"source": "init_demo_student_data"},
            output_payload={"status": "seeded"},
            status="succeeded",
            duration_ms=1200,
        )
        db.add(agent_run)
        await db.flush()

        diagnosis = DiagnosisReport(
            user_id=user.id,
            course_id=course.id,
            report_type="practice",
            summary="最近练习正确率约 72%，主要薄弱点集中在栈队列概念辨析和二叉树遍历。",
            mastery_result={"accuracy": 0.72, "total_questions": len(blueprint["quiz_questions"])},
            weak_points=[
                {"name": "循环队列判空判满", "evidence": "多选题漏选"},
                {"name": "二叉树遍历", "evidence": "填空题需要强化"},
            ],
            error_patterns=[{"pattern": "概念混淆", "count": 2}],
            recommended_actions=[
                {"type": "resource", "title": "查看循环队列流程图"},
                {"type": "quiz", "title": "重做栈与队列专项练习"},
            ],
            generated_by_agent_run_id=agent_run.id,
        )
        db.add(diagnosis)
        await db.flush()

        evolution_event = EvolutionEvent(
            user_id=user.id,
            course_id=course.id,
            trigger_type="auto_diagnosis",
            focus="根据演示诊断生成学习策略草稿，不自动应用。",
            input_snapshot={"diagnosis_id": str(diagnosis.id), "accuracy": 0.72},
            strategies_generated=1,
            status="completed",
        )
        db.add(evolution_event)
        strategy = EvolutionStrategy(
            user_id=user.id,
            course_id=course.id,
            strategy_type="review_strategy",
            before_value={"daily_focus": "泛读资料"},
            after_value={"daily_focus": "先看图解，再做栈队列错题复盘"},
            description="建议把每日复习顺序调整为图解讲解、错题回看、短练习。",
            status="draft",
            risk_level="low",
            evidence=[
                {"type": "diagnosis", "id": str(diagnosis.id)},
                {"type": "mistake", "summary": "栈队列概念混淆"},
            ],
            version_no=1,
        )
        db.add(strategy)
        await db.flush()

        path = LearningPath(
            user_id=user.id,
            course_id=course.id,
            title="两周数据结构补弱路径",
            goal="优先补齐栈队列与二叉树遍历",
            reason="由演示画像、错题和诊断共同生成。",
            status="active",
            progress=Decimal("35.00"),
            strategy_version_id=strategy.id,
        )
        db.add(path)
        await db.flush()
        for index, item in enumerate(
            [
                ("阅读栈与队列 Wiki", "wiki", "先统一概念边界。", "stack-queue"),
                ("查看循环队列流程图", "resource", "用图解检查判空判满条件。", "stack-queue"),
                ("完成二叉树遍历短练习", "quiz", "巩固递归顺序。", "binary-tree"),
            ],
            start=1,
        ):
            title, item_type, reason, key = item
            db.add(
                LearningPathItem(
                    path_id=path.id,
                    knowledge_id=knowledge_by_key[key].id,
                    wiki_page_id=wiki_by_key.get(key).id if key in wiki_by_key else None,
                    title=title,
                    item_type=item_type,
                    order_index=index,
                    status="completed" if index == 1 else "pending",
                    reason=reason,
                    estimated_minutes=20,
                    completed_at=now if index == 1 else None,
                )
            )

        for index, title in enumerate(
            [
                "优先复习循环队列判空判满",
                "用思维导图复盘栈与队列",
                "完成二叉树遍历 10 分钟短练",
            ],
            start=1,
        ):
            target = resources[min(index - 1, len(resources) - 1)]
            db.add(
                Recommendation(
                    user_id=user.id,
                    course_id=course.id,
                    recommendation_type="resource" if index < 3 else "quiz",
                    target_id=target.id,
                    title=title,
                    reason="基于最新画像、诊断和错题记录主动推送。",
                    priority=10 - index,
                    strategy_version_id=strategy.id,
                    status="pending",
                )
            )

        for event_type in blueprint["learning_events"]:
            db.add(
                LearningRecord(
                    user_id=user.id,
                    course_id=course.id,
                    knowledge_id=knowledge_by_key["stack-queue"].id,
                    event_type=event_type,
                    event_source="demo_seed",
                    event_payload={"demo": True, "course_code": DEMO_COURSE_CODE},
                )
            )

        conversation = AgentConversation(
            user_id=user.id,
            course_id=course.id,
            thread_id=f"demo-{username}-{DEMO_COURSE_CODE}",
            title="演示：数据结构学习助手",
            status="active",
            summary="演示会话展示画像、检索、资源生成、诊断和推荐闭环。",
            extra_meta={"demo": True},
            last_message_at=now,
        )
        db.add(conversation)
        await db.flush()

        task = AgentTask(
            user_id=user.id,
            course_id=course.id,
            conversation_id=conversation.id,
            thread_id=conversation.thread_id,
            task_goal="根据我的薄弱点生成下一步学习建议，并给出图解资源。",
            task_type="recommendation",
            status="succeeded",
            plan_json={"steps": ["search_course_knowledge", "generate_diagram", "refresh_recommendations"]},
            input_payload={"goal": "演示主动推荐"},
            intent_payload={"intent": "recommendation"},
            risk_level="low",
            requires_confirmation=False,
            confirmed_at=now,
            started_at=now,
            finished_at=now,
            iteration_count=1,
            tool_call_count=3,
            replan_count=0,
            last_event_at=now,
        )
        db.add(task)
        await db.flush()

        for index, action in enumerate(
            ["search_course_knowledge", "generate_diagram", "refresh_recommendations"],
            start=1,
        ):
            db.add(
                AgentTaskStep(
                    task_id=task.id,
                    step_index=index,
                    agent_name="OrchestratorAgent",
                    action=action,
                    expected_output="演示工具执行结果",
                    status="succeeded",
                    input_payload={"demo": True},
                    output_payload={"ok": True},
                    evidence=[f"{action} completed"],
                    artifact_refs=[],
                    tool_call_id=f"demo-tool-{index}",
                    node_name="execute_tool",
                    decision_summary="演示数据初始化生成的工具步骤",
                    started_at=now,
                    finished_at=now,
                )
            )
            db.add(
                AgentTaskEvent(
                    task_id=task.id,
                    conversation_id=conversation.id,
                    sequence_no=index,
                    event_type="tool_completed",
                    payload={"tool_name": action, "status": "succeeded", "demo": True},
                )
            )

        db.add_all(
            [
                AgentMessage(
                    conversation_id=conversation.id,
                    user_id=user.id,
                    task_id=task.id,
                    role="user",
                    message_type="text",
                    content="我最近栈和队列总是混，请帮我安排下一步。",
                    payload={"demo": True},
                ),
                AgentMessage(
                    conversation_id=conversation.id,
                    user_id=user.id,
                    task_id=task.id,
                    role="assistant",
                    message_type="text",
                    content="建议先看循环队列流程图，再完成栈与队列专项练习。我已刷新 3 条推荐。",
                    payload={"demo": True, "recommendations_refreshed": 3},
                ),
            ]
        )

        await db.commit()

        from scripts.import_seed_knowledge_graph import import_graph

        seed_graph = await import_graph(course_id=course.id, owner_id=user.id)

        return {
            "username": username,
            "password": password,
            "course_id": str(course.id),
            "course_code": course.course_code,
            "knowledge_points": len(blueprint["knowledge_points"]),
            "wiki_pages": len(blueprint["wiki_pages"]),
            "resources": len(blueprint["resources"]),
            "quiz_questions": len(blueprint["quiz_questions"]),
            "recommendations": 3,
            "learning_events": len(blueprint["learning_events"]),
            "agent_task_id": str(task.id),
            "seed_graph": seed_graph,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a complete demo student learning loop.")
    parser.add_argument("--username", default=DEMO_USERNAME)
    parser.add_argument("--password", default=DEMO_PASSWORD)
    parser.add_argument("--email", default=DEMO_EMAIL)
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep the existing demo user and only refresh the DS-DEMO course.",
    )
    args = parser.parse_args()

    result = asyncio.run(
        ensure_demo_student_data(
            username=args.username,
            password=args.password,
            email=args.email,
            rebuild=not args.keep_existing,
        )
    )
    print("Demo student data initialized")
    print(f"username: {result['username']}")
    print(f"password: {result['password']}")
    print(f"course_code: {result['course_code']}")
    print(f"course_id: {result['course_id']}")
    print(f"knowledge_points: {result['knowledge_points']}")
    print(f"wiki_pages: {result['wiki_pages']}")
    print(f"resources: {result['resources']}")
    print(f"quiz_questions: {result['quiz_questions']}")
    print(f"recommendations: {result['recommendations']}")
    print(f"learning_events: {result['learning_events']}")
    print(f"agent_task_id: {result['agent_task_id']}")
    print(f"seed_graph: {result.get('seed_graph')}")


if __name__ == "__main__":
    main()
