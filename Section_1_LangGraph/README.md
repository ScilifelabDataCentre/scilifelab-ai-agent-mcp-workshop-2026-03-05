# SciLifeLab Workshop: LangGraph AI Agents for Drug Discovery

---

A comprehensive hands-on workshop tutoring participants how to build AI agents using LangGraph, specifically focused on drug discovery applications.

## Workshop Overview

This 75-minute interactive workshop introduces participants to **LangGraph**, a low-level orchestration framework for constructing stateful AI workflows using graphs. Participants will learn to build AI agents that can perform mathematical calculations, search scientific literature, and query drug databases.

### Learning Objectives

By the end of this workshop, participants will:

- Understand core concepts of LangGraph (tools, nodes, edges, state, and memory)
- Create and integrate custom tools for AI agents
- Build a ReAct-style agent from scratch using LLMs and custom tools
- Implement agent memory to maintain conversational context
- Compare custom agents with prebuilt LangGraph agents
- Explore advanced features like error handling and streaming

## Repository Structure

```
workshop/
├── README.md               # This comprehensive guide
├── requirements.txt        # Python dependencies
├── langgraph_lab.ipynb     # Main workshop notebook (exercises)
├── langgraph_answer.ipynb  # Solution notebook with completed code
├── .env                    # environment files (contain your API keys)
├── images/                 # Workshop assets
├── utils/                  # Several useful functions
```

## Getting Started

**Change directory to Section 1**

```bash
cd Section_1_LangGraph
```

**Build Docker Image**

```bash
docker build -t scilifelab-langgraph-jupyter .
```

**Run Docker container**

```bash
docker run --rm -it -p 8888:8888 -v "$(pwd)":/home/workshop/app  \--env-file .env scilifelab-langgraph-jupyter
```

**Access and practice** 

Go to localhost:8888 on your browser and starting the lab

## Detailed Notebook Content

### langgraph_lab.ipynb (Workshop Exercises)

**Structure**: 9 parts with progressive complexity

- **Interactive Design**: TODO sections for hands-on coding
- **Guided Learning**: Step-by-step instructions with code templates
- **Domain Focus**: Drug discovery use cases throughout
- **Progressive Complexity**: From simple tools to complete agent systems

### langgraph_answer.ipynb (Complete Solutions)

**Purpose**: Reference implementation with all exercises completed

- **Full Code**: Working solutions for all TODO sections
- **Error Handling**: Robust implementations with try-catch blocks
- **Best Practices**: Proper Python coding standards and documentation
- **Testing Ready**: Includes visualization and interaction loops
