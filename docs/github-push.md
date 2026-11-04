# GitHub 上传步骤

```powershell
cd D:\cloud_tools\RAGentHub

# 1. 初始化 git
git init
git branch -M main

# 2. 首次提交
git add .
git commit -m "feat: RAGentHub initial scaffold - FastAPI + LangChain RAG, Spring Boot backend, multi-domain"

# 3. 在 GitHub 网页上新建一个空仓库（不要勾 README），名字建议 ragenthub
#    然后：
git remote add origin https://github.com/<你的用户名>/ragenthub.git
git push -u origin main
```

## 推荐仓库描述

- **About**：Enterprise multi-agent RAG platform, re-skinnable across finance / gov / medical. Spring Boot + FastAPI + LangChain + Chroma.
- **Topics**：`rag` `agent` `langchain` `spring-boot` `fastapi` `chromadb` `llm` `knowledge-base`
