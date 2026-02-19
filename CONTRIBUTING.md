# Tide-Watcher 开发指南

## 快速开始

### 环境准备
```bash
cd backend
cp .env.example .env          # 复制环境变量模板
# 编辑 .env，填入你的 ZHITU_TOKEN
pip install -r requirements.txt
```

### 启动开发服务器
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## 如何添加新的选股策略

1. 复制模板文件：
```bash
cp backend/app/strategies/_template.py backend/app/strategies/my_strategy.py
```

2. 编辑策略文件，修改策略名称和筛选条件

3. 重启服务器，策略自动注册生效

## 如何添加新的数据源

1. 在 `backend/app/data/` 创建 `source_xxx.py`
2. 继承 `DataSource` 基类，实现所有抽象方法
3. 在 `config.py` 添加对应的配置项

## 目录职责速查

| 目录 | 职责 | 修改频率 |
|------|------|---------|
| `strategies/` | 选股策略定义 | **高**（日常开发） |
| `api/` | REST 接口 | 中 |
| `data/` | 外部数据获取 | 低 |
| `store/` | 数据库操作 | 低 |
| `engine/` | 策略引擎核心 | 极低 |

## Git 提交规范

- 提交信息使用中文
- 格式：`[模块] 描述`
- 示例：`[策略] 新增连板股筛选策略` / `[数据] 修复ZhituAPI超时处理`
