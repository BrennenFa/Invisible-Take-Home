# AI Usage Log - Banking REST API Project

## Tools Used
- Claude Code
- ChatGPT (web)
- Gemini (web)


---

## Example Prompts and Iterations

**Prompt:** "Where are id's managed? Are they incremental? If so, change to uuid?"

This prompt allowed me to easily validate notions I had about the project and make quick changes. In this case, the change wouldn't be hard, but it would be very manual and time consuming. AI allows me to override much of that work and focus on the important, difficult parts. Additionally, it shows that the AI will not always make the correct decision initially.



**Prompt:** "So im using a sqlite db.... is there anything u can do to help manage concurrency with it?"
**Follow Up:** "If i have a .wal.... and its used locally... how should i set it to backup? i currently have 500 pages, but should i have it be intermittent?"

This prompt allowed me get a good understanding of system design issues. In software engineering, there are various important concepts. With the prompts above, it allowed me to understand the weaknesses of my current approach (lack of concurrency) and possible solutions. 

Further, rather than simply accepting the solution, I made sure to understand it and it's weaknesses. This particular prompt made me think of implementing a backup system. While AI helped me reach the conclusion of it not being essential at this moment, it did help me understand the problem in a more general way.



**Prompt:** "How do these models look? Are there any changes you would make"
**Response (parphrased):** "I would take out the CVV to ensure your system is PCI DSS complaint"
**Response:** "What is that? How would I handle testing? Could I have it return the CVV upon card creation"

A big use case of AI is domain knowledge. Before this, I had no idea that CVV's were not stored. By having AI look at my code, its able to understand how systems are supposed to work in a non-technical way and I can learn more about problems I don't know exist. Additionally, it's able to give me a good check to make sure my work is in the right place.


---


## Challenges AI helped with

### Challenge 1: Implementing simple changes
AI is very good at implementing area wide changes. For example, in the UUID example above or putting in rate limiters for the application. This saves a lot of meaningless time.

### Challenge 2: Easy Creation of Skeleton Tests and Routes
For very simple routes and tests, AI is able to do much of the work. I know how a get transaction route would work, but implementing it is time consuming rather than something you have to think about. The same goes for testing, where I can understand the use case very well, such as an authorized or unauthorized get method, but implementation is not always quick. AI helps to eliminate these mundane tasks.

### Challenge 3: Complex Transaction/validation Logic
This is very similar to the idea above. Validtion comes in many forms in many routes, schemas, and logic (eg: is a credit card useable?). AI is smart enough to understand the basics and implement most of it for me.

### Challenge 4: Choice Validation
AI is very good at discussing architecture. I can frequently ask it what it thinks I should do for prioritized elements, such as security (eg: how secure is this? what should i add?). As it has access to the code base and tehcnical knowledge, it can help me understand what to implement.
---

## Areas Where Manual Intervention Was Necessary

### 1. System Decisions
As a human, I need to understand how the system works as a whole. This means I understand what to focus on and prioritize. For example, I frequently made choices and guided the AI to support concurrency, idempotency, and security (more below). I also new the level of complexity required. At one point, the AI tried to convince me to implement a Redis cache for idempotency. However, due to the massive time and setup this would take, not to mention it going somewhat against the instructions, I decided agaisnt. While it can give me decisions, it's up to me to make the best final choice.

### 2. Security
AI is infamous for creating security vulnerabilities. In one instance, I had an issue with a database url being committed in the following format: os.getenv("DB_URL", "sqlite:///./db/database.db"). While this was not a huge risk, it is very important that manual intervention and code review is done to ensure risks are not prevalent.









