# AI 私教系统 — 技术方案文档

> 版本：1.0 | 最后更新：2026-09-04

---

## 1. 技术架构概览

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React 18)               │
│  Login │ Dashboard │ Documents │ Quiz │ Review │ Chat│
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│                   Gateway (FastAPI)                  │
│        Auth │ Proxy │ Rate Limit │ Error Handle     │
└───┬──────────┬──────────┬──────────┬───────────┬────┘
    │          │          │          │           │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌────▼────┐
│Knowl- │ │  RAG  │ │Feyn-  │ │ Quiz  │ │ Review  │
│edge   │ │ Agent │ │ man   │ │ Agent │ │ Agent   │
│Agent  │ │       │ │ Agent │ │       │ │         │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └────┬────┘
    │         │         │         │           │
┌───▼─────────▼─────────▼─────────▼───────────▼────┐
│            PostgreSQL 16 + pgvector               │
│     documents │ chunks │ quizzes │ reviews │ users│
└──────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                    Redis 7                           │
│              Session Cache │ Rate Limit              │
└─────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 前端 | React | 18 | UI 框架 |
| 前端 | TypeScript | 5.x | 类型安全 |
| 前端 | Vite | 5.x | 构建工具 |
| 前端 | TailwindCSS | 3.x | 样式 |
| 前端 | Lucide React | - | 图标 |
| 后端 | Python | 3.11 | 运行时 |
| 后端 | FastAPI | 0.110+ | Web 框架 |
| 后端 | SQLAlchemy | 2.0 | ORM（async） |
| 后端 | Pydantic | 2.0 | 数据验证 |
| 数据库 | PostgreSQL | 16 | 主数据库 |
| 数据库 | pgvector | - | 向量检索 |
| 缓存 | Redis | 7 | 缓存/会话 |
| LLM | SiliconFlow | - | LLM + Embedding |
| 爬虫 | Jina Reader | - | URL 内容抓取 |
| 容器 | Docker Compose | - | 部署编排 |

---

## 2. 服务拆分

### 2.1 服务列表

| 服务 | 端口 | 职责 | 技术 |
|------|------|------|------|
| `gateway` | 8000 | API 网关、认证、请求路由 | FastAPI |
| `knowledge-agent` | 8001 | 文档管理、导入、切分、向量化 | FastAPI |
| `rag-agent` | 8002 | 语义搜索、查询重写 | FastAPI |
| `feynman-agent` | 8003 | 费曼学习法对话、评分 | FastAPI |
| `quiz-agent` | 8004 | 测验生成、批改、错题管理 | FastAPI |
| `review-agent` | 8005 | 复习计划、SM-2 算法 | FastAPI |
| `progress-agent` | 8006 | 学习统计、进度追踪 | FastAPI |
| `web-app` | 3000 | 前端静态资源 | Nginx + React |
| `postgres` | 5432 | 数据库 | PostgreSQL 16 |
| `redis` | 6379 | 缓存 | Redis 7 |

### 2.2 服务间通信

```
Gateway → Knowledge Agent  : HTTP REST (文档 CRUD)
Gateway → RAG Agent        : HTTP REST (搜索)
Gateway → Feynman Agent    : HTTP REST + SSE (对话)
Gateway → Quiz Agent       : HTTP REST (测验)
Gateway → Review Agent     : HTTP REST (复习)
Gateway → Progress Agent   : HTTP REST (统计)
```

所有服务间通信通过 Gateway 代理，前端不直接访问后端 Agent。

---

## 3. 数据模型

### 3.1 ER 关系图

```
users ──┬── documents ──── chunks ──── mastery_records
        │                │
        │                └── review_schedule ──── review_logs
        │
        ├── quizzes ──── wrong_questions
        │
        ├── feynman_sessions
        │
        ├── threads ──── runs
        │
        └── import_batches
```

### 3.2 核心表结构

#### users

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| email | VARCHAR(255) | 邮箱（唯一） |
| username | VARCHAR(100) | 用户名 |
| hashed_password | VARCHAR(255) | bcrypt 哈希密码 |
| avatar_url | VARCHAR(500) | 头像 URL |
| created_at | TIMESTAMP | 创建时间 |

#### documents

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → users |
| title | VARCHAR(500) | 文档标题 |
| source_type | VARCHAR(20) | 来源类型：url/file/manual |
| source_url | VARCHAR(2000) | 来源 URL |
| content | TEXT | 文档内容 |
| status | VARCHAR(20) | 状态：pending/processing/completed/failed |
| tags | JSON | 标签数组 |
| chunk_count | INTEGER | 知识块数量 |
| batch_id | UUID | 批量导入批次 ID |
| deleted_at | TIMESTAMP | 逻辑删除时间 |
| created_at | TIMESTAMP | 创建时间 |
| processed_at | TIMESTAMP | 处理完成时间 |

#### chunks

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| document_id | UUID | 外键 → documents |
| content | TEXT | 知识块内容 |
| embedding | VECTOR(1024) | 向量嵌入 |
| metadata | JSONB | 元数据（token数、字符数等） |
| chunk_index | INTEGER | 块索引 |
| token_count | INTEGER | Token 数量 |
| deleted_at | TIMESTAMP | 逻辑删除时间 |
| created_at | TIMESTAMP | 创建时间 |

**索引：**
- `idx_chunks_document` — 按文档查询
- `idx_chunks_embedding` — HNSW 向量索引（cosine）

#### quizzes

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → users |
| scope | VARCHAR(50) | 测验范围 |
| topic | VARCHAR(200) | 主题 |
| questions | JSON | 题目列表 |
| total_questions | INTEGER | 总题数 |
| status | VARCHAR(20) | 状态 |
| created_at | TIMESTAMP | 创建时间 |

#### wrong_questions

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| quiz_id | UUID | 外键 → quizzes |
| question | JSON | 题目内容 |
| user_answer | TEXT | 用户答案 |
| correct_answer | TEXT | 正确答案 |
| explanation | TEXT | 解析 |
| review_count | INTEGER | 复习次数 |
| mastered | BOOLEAN | 是否已掌握 |
| created_at | TIMESTAMP | 创建时间 |

#### review_schedule

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → users |
| chunk_id | UUID | 外键 → chunks |
| mastery_score | FLOAT | 掌握度 0-100 |
| ease_factor | FLOAT | SM-2 易度因子 |
| interval_days | INTEGER | 复习间隔天数 |
| review_count | INTEGER | 已复习次数 |
| next_review | TIMESTAMP | 下次复习时间 |
| status | VARCHAR(20) | 状态 |
| created_at | TIMESTAMP | 创建时间 |

#### review_logs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| schedule_id | UUID | 外键 → review_schedule |
| chunk_id | UUID | 外键 → chunks |
| quality | INTEGER | 复习质量 0-5 |
| old_interval | INTEGER | 旧间隔 |
| new_interval | INTEGER | 新间隔 |
| old_mastery | FLOAT | 旧掌握度 |
| new_mastery | FLOAT | 新掌握度 |
| reviewed_at | TIMESTAMP | 复习时间 |

#### threads / runs

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → users |
| agent_type | VARCHAR(50) | Agent 类型 |
| status | VARCHAR(20) | 状态 |
| state | JSON | 会话状态 |
| created_at | TIMESTAMP | 创建时间 |

---

## 4. API 设计

### 4.1 Gateway 路由

#### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/auth/me` | 获取当前用户 |

#### 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/import` | 导入文档 |
| POST | `/api/documents` | 创建文档 |
| GET | `/api/documents` | 文档列表 |
| GET | `/api/documents/{id}` | 文档详情 |
| DELETE | `/api/documents/{id}` | 删除文档 |

#### 测验

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/quiz/generate` | 生成测验 |
| POST | `/api/quiz/submit` | 提交答案 |
| GET | `/api/quiz/wrong-book` | 错题本 |
| POST | `/api/quiz/wrong-book/{id}/mastered` | 标记已掌握 |

#### 复习

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/review/pending` | 待复习列表 |
| POST | `/api/review/submit` | 提交复习 |
| GET | `/api/review/stats` | 复习统计 |

#### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/threads` | 创建会话 |
| GET | `/api/threads` | 会话列表 |
| GET | `/api/threads/{id}` | 会话详情 |
| DELETE | `/api/threads/{id}` | 删除会话 |
| POST | `/api/runs` | 创建运行 |
| GET | `/api/runs/stream` | SSE 流式输出 |

#### 费曼

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/feynman/start` | 开始费曼会话 |
| POST | `/api/feynman/explain` | 提交解释 |
| POST | `/api/feynman/add-to-review` | 加入复习 |

#### 进度

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/progress/dashboard` | 仪表盘数据 |
| GET | `/api/progress/mastery` | 掌握度分析 |

#### 搜索

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/search/query` | 语义搜索 |
| POST | `/api/search/rewrite` | 查询重写 |

---

## 5. 核心算法

### 5.1 文档处理流程

```
URL/文件输入
    │
    ▼
Jina Reader / 文件读取
    │
    ▼
HTML 清理 → Markdown 转换
    │
    ▼
文档切分（固定大小 + 重叠）
    │
    ▼
Embedding（BAAI/bge-m3, 1024维）
    │
    ▼
存储到 PostgreSQL + pgvector
```

**切分策略：**
- 块大小：约 500 字符
- 重叠：50 字符
- 保留段落边界

### 5.2 SM-2 间隔重复算法

```python
def sm2(quality: int, repetition: int, ease_factor: float, interval: int):
    """
    quality: 复习质量 0-5
        0 = 完全忘记
        1 = 错误，但看到答案后想起
        2 = 错误，但答案很熟悉
        3 = 正确，但很困难
        4 = 正确，经过思考后回忆起
        5 = 完美，立即回忆起
    
    Returns: (new_repetition, new_ease_factor, new_interval)
    """
    if quality >= 3:  # 正确
        if repetition == 0:
            new_interval = 1
        elif repetition == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease_factor)
        new_repetition = repetition + 1
    else:  # 错误
        new_repetition = 0
        new_interval = 1
    
    new_ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease_factor = max(1.3, new_ease_factor)
    
    return new_repetition, new_ease_factor, new_interval
```

### 5.3 掌握度计算

```python
def calculate_mastery(quiz_score: float, feynman_score: float, review_quality: float):
    """
    多维度掌握度 = 加权平均
    - 测验得分权重: 40%
    - 费曼评分权重: 30%
    - 复习表现权重: 30%
    """
    weights = {"quiz": 0.4, "feynman": 0.3, "review": 0.3}
    mastery = (
        quiz_score * weights["quiz"] +
        feynman_score * weights["feynman"] +
        review_quality * weights["review"]
    )
    return min(100, max(0, mastery))
```

### 5.4 文档去重

```python
def check_duplicate(user_id, source_type, source_url=None, content=None):
    """
    URL 去重: source_url + user_id 唯一
    文件去重: SHA256(content) + user_id 唯一
    """
    if source_type == "url":
        query = select(Document).where(
            Document.user_id == user_id,
            Document.source_url == source_url,
            Document.deleted_at.is_(None)
        )
    elif source_type == "file":
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        query = select(Document).where(
            Document.user_id == user_id,
            Document.file_hash == file_hash,
            Document.deleted_at.is_(None)
        )
    return db.execute(query).scalar_one_or_none()
```

---

## 6. LLM 集成

### 6.1 配置

```python
# .env
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_EMBEDDING_MODEL=BAAI/bge-m3
```

### 6.2 自动降级

LLM 调用失败时自动切换备用模型：

```
主模型调用失败
    │
    ▼
尝试备用模型 1
    │
    ▼
尝试备用模型 2
    │
    ▼
返回错误
```

### 6.3 Embedding

- 模型：BAAI/bge-m3
- 维度：1024
- 批量处理：支持
- 存储格式：pgvector VECTOR(1024)

---

## 7. 前端架构

### 7.1 目录结构

```
web-app/src/
├── components/      # 通用组件
├── pages/           # 页面组件
│   ├── Login.tsx
│   ├── Dashboard.tsx
│   ├── Documents.tsx
│   ├── Chat.tsx
│   ├── Quiz.tsx
│   ├── Review.tsx
│   └── Progress.tsx
├── services/        # API 服务
│   └── api.ts
├── types/           # TypeScript 类型
│   └── index.ts
├── App.tsx
└── main.tsx
```

### 7.2 路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/login` | Login | 登录/注册 |
| `/` | Dashboard | 仪表盘 |
| `/documents` | Documents | 文档管理 |
| `/chat` | Chat | AI 对话 |
| `/quiz` | Quiz | 智能测验 |
| `/review` | Review | 复习计划 |
| `/progress` | Progress | 学习进度 |

### 7.3 API 调用

所有 API 请求通过 Gateway 代理：

```typescript
// services/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
```

---

## 8. 部署方案

### 8.1 Docker Compose

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
  gateway:
    build: ./gateway
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
  
  knowledge-agent:
    build: ./knowledge-agent
    ports: ["8001:8001"]
    depends_on: [postgres]
  
  rag-agent:
    build: ./rag-agent
    ports: ["8002:8002"]
    depends_on: [postgres]
  
  # ... 其他服务类似
```

### 8.2 环境变量

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://ai_tutor:postgres@postgres:5432/ai_tutor

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_SECRET=your-secret-key

# LLM
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
DEFAULT_EMBEDDING_MODEL=BAAI/bge-m3

# 爬虫
JINA_API_KEY=
```

### 8.3 启动命令

```bash
# 构建并启动所有服务
docker compose up -d --build

# 查看日志
docker compose logs -f [service-name]

# 重启单个服务
docker compose restart [service-name]

# 停止所有服务
docker compose down
```

---

## 9. 测试策略

### 9.1 测试金字塔

```
         ┌─────────┐
         │  E2E    │  ← Playwright（规划中）
         │  Tests  │
        ┌┴─────────┴┐
        │ Integration│  ← pytest + httpx
        │   Tests    │
      ┌─┴───────────┴─┐
      │   Unit Tests   │  ← pytest（275个，92%覆盖）
      └────────────────┘
```

### 9.2 当前测试覆盖

| 模块 | 测试数 | 覆盖率 |
|------|--------|--------|
| Gateway | 85 | 94% |
| Knowledge Agent | 52 | 91% |
| RAG Agent | 18 | 88% |
| Quiz Agent | 22 | 90% |
| Review Agent | 15 | 89% |
| Progress Agent | 12 | 87% |
| Feynman Agent | 18 | 92% |
| Shared | 35 | 95% |
| Integration | 10 | - |
| **总计** | **275** | **92%** |

### 9.3 测试运行

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块
python -m pytest tests/unit/test_gateway_auth.py -v

# 查看覆盖率
python -m pytest tests/ --cov=. --cov-report=term-missing
```

---

## 10. 已知问题与技术债

### 10.1 已修复

| 问题 | 修复方案 |
|------|---------|
| 文档导入 404 | Gateway 代理路径修正 |
| import_batches 约束缺失 'failed' | ALTER TABLE 添加约束 + 迁移 003 |
| Embedding 类型不匹配 | Column(String) → Column(Vector(1024)) |
| 硅基流动 API Key 占位符 | 更新 .env |
| 前端导入格式不匹配 | Documents.tsx 修正请求体 |

### 10.2 待处理

| 问题 | 优先级 | 说明 |
|------|--------|------|
| E2E 测试缺失 | 高 | Playwright 测试框架已安装，脚本待完成 |
| Chunk 逻辑删除未在搜索中过滤 | 中 | RAG 搜索 SQL 需添加 deleted_at 过滤 |
| Jina 爬虫无 API Key | 中 | 部分 URL 抓取失败 |
| asyncio.run() 弃用警告 | 低 | Python 3.12+ 兼容性 |

---

## 11. 扩展方向

### 11.1 短期（1-2 周）

- 完成 E2E 测试脚本
- 修复 Chunk 逻辑删除过滤
- 添加 Jina API Key 配置

### 11.2 中期（1-2 月）

- 文档预览功能
- 测验历史统计
- 学习成就系统
- 邮件通知复习提醒

### 11.3 长期（3+ 月）

- 多语言支持
- 团队学习空间
- API 开放接口
- 移动端适配
