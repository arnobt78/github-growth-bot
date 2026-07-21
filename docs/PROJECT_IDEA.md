# Project Ideas & Tips & Tricks & follow thoughts in improving development process

## 12 Architecture Concepts Every Developer Should Know

1️⃣ Load Balancing – Spread traffic across servers to avoid crashes and handle spikes.
2️⃣ Caching – Store data temporarily to reduce DB load and improve speed.
3️⃣ CDN – Deliver content from the nearest location to reduce global latency.
4️⃣ Message Queue – Use async processing to avoid failure chains between services.
5️⃣ Publish–Subscribe – One event, multiple listeners. Keeps services loosely connected.
6️⃣ API Gateway – Single entry point for auth, routing, logging and rate limiting.
7️⃣ Circuit Breaker – Stop calling failing services to prevent system-wide crashes.
8️⃣ Service Discovery – Automatically find running services in dynamic environments.
9️⃣ Sharding – Split large databases when one server is not enough.
🔟 Rate Limiting – Protect systems from abuse, bots and traffic floods.
1️⃣1️⃣ Consistent Hashing – Smart data distribution with minimal reshuffling during scaling.
1️⃣2️⃣ Auto Scaling – Automatically increase/decrease servers based on traffic.

🎯 Final Thought
Junior mindset: “Does my API work?”
Senior mindset: “Will this system survive heavy traffic, failure and scale?”

## The end of the useMemo and useCallback era is officially here

If you’ve been building complex React applications for a while, you know the struggle. We’ve all spent hours hunting down unnecessary re-renders and wrapping half of our codebase in memoization hooks just to keep the UI smooth. It cluttered the code, increased cognitive load, and was incredibly easy to get wrong.
With the React Compiler, manual memoization is finally becoming a thing of the past.
It now analyzes your code and automatically applies these optimizations under the hood, right out of the box.
What this actually means for frontend developers:
✅ Cleaner code: Components are much easier to read and maintain without the hook boilerplate.
✅ Performance by default: The UI stays fast without requiring you to manually babysit every render cycle.
✅ Faster development: You can focus on building features and architecture instead of debugging dependency arrays.
It’s a massive step forward for the React ecosystem.

## Most developers accidentally make async JavaScript slower than it needs to be

A lot of people write async code like this:

await first request
wait…
await second request
wait…
await third request

It works.

But if those requests are independent, you’re wasting time.

The better approach:

✅ run them in parallel with Promise.all()

## That small change can make your code feel much faster without changing the feature at all

Simple rule:
If task B depends on task A → use sequential await
If tasks are independent → use Promise.all()

If you use Cursor, you’re likely wasting 40% of your budget on "Here is the updated code" and "I hope this helps."

You can save a lot by adding below rule.
Copy-paste this into your project repository

.cursor/rules/llm-token-efficiency.mdc

---

description: Enforce token-efficient, code-centric responses
alwaysApply: true

---

### TOKEN EFFICIENCY RULES

- No Yapping: no intros, no outros, no filler.
- Surgical Strikes: only show changed code blocks. Never full files.
- Expert Mode: zero explanations. No why/how unless asked.
- Dry Output: bullets only if needed. No paragraphs.
- Minimal Code: no comments, no boilerplate.

## If Claude keeps giving you inconsistent results, your setup is the problem, not Claude

Here's what separates a messy Claude Code setup from a high-performing one:

▪️ Don't leave CLAUDE.md empty or vague
Do define your tech stack, architecture, and conventions clearly, it's the first thing Claude reads every session

▪️ Don't mix personal preferences into shared project files
Do use CLAUDE.local.md for individual overrides so your workflow doesn't break your teammates'

▪️ Don't re-explain your tooling every session
Do configure mcp.json once, GitHub, JIRA, Slack, databases all connected and version-controlled

▪️ Don't write one giant instruction file for everything
Do use .claude/rules/ to separate concerns, code style, testing standards, API conventions load contextually

▪️ Don't repeat the same prompts for recurring workflows
Do create .claude/commands/ slash commands, one keystroke runs your entire review or deploy process

▪️ Don't let Claude operate without guardrails
Do set up .claude/hooks/ to validate, lint, and block unsafe operations automatically

▪️ Don't overload a single conversation with every task
Do delegate to .claude/agents/ specialized sub-agents with isolated context for code review, security, and more

Your Claude Code setup is either working for your team or against it. Structure it once. Benefit from it forever.

## Every Node.js developer should understand this Docker mistake. It costs minutes every build

Docker layer caching is one of those things nobody explains until you've already wasted hours waiting for builds.

Here's the mistake I see in almost every first Dockerfile:

### ❌ Slow — reinstalls ALL node_modules on every code change

FROM node:20-alpine
WORKDIR /app
COPY . . # copies everything first
RUN npm install # then installs
CMD ["node", "dist/main.js"]

The problem: COPY . . copies your source code before npm install. Every time you change a single line of TypeScript, Docker sees the layer as changed, invalidates the cache, and reinstalls all dependencies from scratch.

For a project with 400 packages, that's 90 seconds of wasted build time. Every. Single. Change.

### ✅ Fast — only reinstalls when package.json changes

FROM node:20-alpine AS builder
WORKDIR /app

### Copy dependency files FIRST (rarely changes)

COPY package\*.json ./
RUN npm ci # cache hit unless package.json changed

### THEN copy source code (changes often)

COPY . .
RUN npm run build

### Production stage — lean image

FROM node:20-alpine AS production
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
CMD ["node", "dist/main.js"]

The principle: things that change less frequently go higher in the Dockerfile.

Three more rules I follow on every project:

→ Use node:alpine over node:latest — image size drops from ~1GB to ~180MB
→ Use npm ci not npm install in CI/CD — deterministic, no lock file surprises
→ Always use a multi-stage build — your production image should never contain TypeScript source, devDependencies, or build tools

Build time on a real NestJS project before this pattern: 4 minutes 20 seconds.
After: 38 seconds (cache hit), 2 minutes 10 seconds (full rebuild).

## Load Balancer vs Reverse Proxy — What's the Difference?

Modern applications and websites handle large amounts of traffic. Two of the main instruments to ensure the smooth operation of large-scale systems are load balancers and reverse proxies.

However, they approach traffic management in slightly different ways:

𝗟𝗼𝗮𝗱 𝗯𝗮𝗹𝗮𝗻𝗰𝗲𝗿𝘀 are concerned with routing client requests across multiple servers to 𝗱𝗶𝘀𝘁𝗿𝗶𝗯𝘂𝘁𝗲 𝗹𝗼𝗮𝗱 and 𝗽𝗿𝗲𝘃𝗲𝗻𝘁 𝗯𝗼𝘁𝘁𝗹𝗲𝗻𝗲𝗰𝗸𝘀. This helps maximize throughput, reduce response time, and optimize resource use.

𝗟𝗼𝗮𝗱 𝗯𝗮𝗹𝗮𝗻𝗰𝗲𝗿 𝗶𝗻 𝗮𝗰𝘁𝗶𝗼𝗻:

𝟭) Client requests are sent to the load balancer instead of directly to the server(s) hosting the application.

𝟮) A server is chosen from the load balancer's list using a predetermined algorithm.

𝟯) The request is forwarded to the selected server.

𝟰) The server processes the requests and sends the response back to the load balancer.

𝟱) The load balancer forwards the response to the client.

A 𝗿𝗲𝘃𝗲𝗿𝘀𝗲 𝗽𝗿𝗼𝘅𝘆 is a server that sits between external clients and internal applications. While reverse proxies can distribute load as a load balancer would, they provide advanced features like SSL termination, caching, and security. Reverse proxies are 𝗺𝗼𝗿𝗲 𝗰𝗼𝗻𝗰𝗲𝗿𝗻𝗲𝗱 𝘄𝗶𝘁𝗵 𝗹𝗶𝗺𝗶𝘁𝗶𝗻𝗴 𝗮𝗻𝗱 𝘀𝗮𝗳𝗲𝗴𝘂𝗮𝗿𝗱𝗶𝗻𝗴 𝘀𝗲𝗿𝘃𝗲𝗿 𝗮𝗰𝗰𝗲𝘀𝘀.

Whilst load balancers and reverse proxies possess distinct functionalities, in practice the lines can blur, as many tools act as both a load balancer and reverse proxy. For example, tools like Nginx can perform both roles depending on their configuration.

## Client-side data normalization — storing state like a database

Data normalization in client apps is an idea that blew my mind when I first experienced its benefit. The core idea is to structure the data to reduce redundancy and improve data integrity. Instead of having nested data, entities store references to other entities via keys, similar to foreign keys in databases.

This practice is commonly done in complex client apps like Facebook, Instagram, X, LinkedIn.

⬇️ How does it work?

Typically, when data is fetched from the server, it's directly displayed and then cached, no additional processing done. Some apps post-process the response by normalizing it and constructing a client-side database out of the response.

E.g., in a timeline feed containing posts made by the same few users, the API may return duplicated user data for each post item, but the client normalizes the response, stores just one instance of that user data, modifies each post to point to that single instance.

👍 Main benefits of this approach

- Data integrity: If a user's details is updated, all posts displaying that user’s data will reflect the update
- Reusable by various parts of the page and even across pages: Components that use that data (or a subset of it) can query it without needing to hit the server. If there's additional data needed, it can immediately display existing data and fetch the missing data while showing placeholders
- Smaller memory footprint: Less data is stored, because there's no duplication

🤔 How is it implemented?

Apps define a client-side schema and converts API responses into a normalized format before storing in the client-side store. This is what the Tanstack DB library does, and it works seamlessly with Tanstack Query.

🤯 Many apps you use are doing it

All of Meta's web applications use a normalized client-side store, thanks to the properties of GraphQL. GraphQL APIs have a schema and every entity has a type. Relay (Meta's data fetching library) makes use of that to understand the relationships between entities and converts GraphQL responses into a normalized shape.

Recently I discovered that apps like LinkedIn and Twitter take it even one step further, normalizing the data on the server, sending down extremely compact responses. The attached image demonstrates this.

If your app is simple or usage session is short, you probably don't need this. This technique benefits client-heavy apps used for long sessions and have frequently-updated data.

## Every time I start a new React project, I copy the same 5 hooks

Not from a library. From my own collection, battle-tested across 15+ production apps.

These aren't clever abstractions. They're boring, reliable utilities that eliminate the same bugs I've fixed dozens of times:

1. useDebounce — stop hammering your API on every keystroke
2. usePrevious — track previous values without infinite re-render loops
3. useLocalStorage — state that survives refresh (SSR-safe, GDPR-aware)
4. useMediaQuery — responsive logic, not just responsive styles
5. useAbortController — cancel requests on unmount, prevent race conditions

5 files. ~150 lines total. Zero dependencies.

Senior engineers don't write more code. They carry better defaults.

## RAG vs. CAG, clearly explained

RAG is the default, but there's a problem most teams don't address.

Every single query retrieves from the vector DB. Even when the data hasn't changed in months.

That's wasted compute, added latency, and cost you don't need to pay.

🔺What RAG does:

Query comes in → embedding model converts it → vectors hit the DB → context retrieved → LLM generates response.

Clean pipeline. But expensive at scale when half your queries are pulling the same static data every time.

🔺What CAG adds:

Cache-Augmented Generation lets the model store static information directly in KV memory.

Instead of retrieving the same policies or documentation on every query, it's already there.

🔺RAG + CAG combined:
→ Static data (policies, docs, reference material) gets cached once in KV memory.
→ Dynamic data (live documents, recent updates) gets fetched via retrieval as usual.

## TanStack moved their blog to RSCs. 153KB less JavaScript. Blocking time: 1,200ms to 260ms

But their RSC model is completely different from Next.js.

Next.js: server owns the tree. You opt into client with 'use client'.

TanStack Start: client owns the tree. RSCs are just streams you fetch and cache. Like useQuery but for server-rendered UI.

Three APIs. That's it:
• renderToReadableStream (server)
• createFromReadableStream (client)
• createFromFetch (convenience)

Caching? TanStack Query. staleTime, refetch, cache keys. Nothing new to learn.

No 'use server' either.
Explicit server functions only.
Smaller attack surface.

As someone who's been using TanStack Router and Query for a while, this is exactly what I wanted. More control, less magic. RSCs without rewriting how I think about my app.

RSCs as a tool you reach for. Not a paradigm you build around.

## Most beginners confuse these AI models

6 model types, explained in simple.

1. Machine Learning Models

• Collect labeled data → examples with correct answers
• Clean and prepare data → remove errors, format properly
• Choose algorithm → like decision tree, regression, etc.
• Train model → learn patterns from data
• Check performance → see how accurate it is
• Adjust settings → improve results
• Make predictions → use on new data
• Track & improve → keep updating over time

Idea: Learning from past data to predict future outcomes

---

1. Deep Learning Models

• Collect large datasets → needs lots of data
• Standardize inputs → make data consistent
• Create neural network → layers of “artificial neurons”
• Forward pass → data flows through network
• Calculate error → compare output vs actual
• Backpropagation → send error backward
• Update weights → improve learning
• Repeat training → many cycles
• Generate output → final prediction/result

Idea: Brain-like system learning complex patterns

---

1. Generative Models

• Train on data → learn patterns
• Understand structure → how data looks
• Take user input → prompt or instruction
• Run through model → process input
• Sample outputs → generate possibilities
• Create content → text, image, etc.
• Improve with feedback → refine results
• Produce final output → polished content

Idea: AI that creates (ChatGPT etc)

---

1. Hybrid Models

• Combine different models → use strengths of each
• Train parts separately → optimize individually
• Build connection logic → link models
• Send input through pipeline → step-by-step flow
• Route based on rules → decide which model to use
• Combine outputs → merge results
• Fix conflicts → resolve differences
• Final output → best combined answer

Idea: Multiple AI systems working together

---

1. NLP Models

• Clean text → remove noise
• Tokenize → break into words/tokens
• Convert to vectors → numbers for AI
• Use attention → focus on important words
• Feed into model → process meaning
• Decode/classify → understand or label
• Clean output → refine text
• Generate output → answer or response

Idea: AI that understands & writes language

---

1. Computer Vision Models
   • Input image → raw picture
   • Resize/normalize → standard format
   • Extract features → edges, shapes, colors
   • Apply CNN layers → detect patterns
   • Identify spatial patterns → objects & positions
   • Classify/detect → what’s in the image
   • Refine results → improve accuracy
   • Output → labels, boxes, predictions

Idea: AI that “sees” & understands images

## Make your product go from "Eh it works" to "Wow, the experience is amazing!" with Vercel's web interface guidelines

Make your product go from "Eh it works" to "Wow, the experience is amazing!" with Vercel's web interface guidelines.

Vercel's web interface guidelines are public for anyone to learn from? It's a gold mine of UI/UX best practices and I learnt a lot from reading through them.

The ones that stood out to me:

→ Minimum loading-state duration. If you show a spinner/skeleton, add a short show-delay (~150–300 ms) & a minimum visible time (~300–500 ms) to avoid flicker on fast responses. The <Suspense> component in React does this automatically.

→ Autofocus for speed. On desktop screens with a single primary input, autofocus. Rarely autofocus on mobile because the keyboard opening can cause layout shift.

→ Deep-link everything. Filters, tabs, pagination, expanded panels, anytime useState is used.

→ Links are links. Use <a> or <Link> for navigation so standard browser behaviors work (Cmd/Ctrl+Click, middle-click, right-click to open in a new tab). Never substitute with <button> or <div> for navigational links.

→ No excessive scrollbars. Only render useful scrollbars; fix overflow issues to prevent unwanted scrollbars. On macOS set "Show scroll bars" to "Always" to test what Windows users would see.

→ Stable skeletons. Skeletons mirror final content exactly to avoid layout shift.

→ Don’t ship the schema. Visual layouts may omit visible labels, but accessible names/labels still exist for assistive tech.

→ Enter submits. When a text input is focused, Enter submits if it's the only control. If there are many controls, apply to the last control.

→ Don’t block typing. Even if a field only accepts numbers, allow any input & show validation feedback. Blocking keystrokes entirely is confusing because the user gets no explanation.

→ Preload wisely. Preload only above-the-fold images; lazy-load the rest.

The full guide spans 7 categories: Interactions, Animations, Layout, Content, Forms, Performance, and Design.

These guidelines are also shipped as an AGENTS.md you can drop into your repo so your coding agents can follow these rules during generation.

## I've completely stopped using Anthropic and OpenAI. Here's why I'm not going back

I've completely stopped using Anthropic and OpenAI. Here's why I'm not going back.

Six months ago I would've called myself a loyal Claude and GPT user. Today my entire workflow runs on Kimi K2.6 and Qwen 3.6. Both open source.

This wasn't ideological. It was practical.

❌ I watched Anthropic silently drop the default "effort" setting to medium, making Claude noticeably dumber, then ship a new version and call it progress.
❌ I watched a 110-person company get banned from API access overnight while still receiving invoices.
❌ Pro plan users were hitting rate limits after barely using the thing, then waiting hours for it to reset then get Claude Code access just removed.
❌ A tokenizer update quietly inflated costs by up to 35%.

And they started banning third-party tools that competed with their own products.

When the company selling you a tool can change what that tool does without telling you, you don't own anything. You're renting.

Meanwhile, open source passed them.

➡️ Kimi K2.6 now sits at #1 on SWE-Bench Pro (58.6), ahead of GPT-5.4, Gemini 3.1 Pro, and Claude Opus 4.6.
➡️ It leads open-weight models on Design Arena, matching Opus 4.7.
➡️ It can coordinate 300 specialized agents across thousands of steps.
➡️ The plan I'm on costs $39/month. No surprise limits. No bans.

And if Moonshot changes their pricing tomorrow, I can pull the weights from Hugging Face and run it locally through Ollama or just use Openrouter. Nobody can take my tools away. That's the difference.

If you're building a business on LLMs, stop tying yourself to one provider. I've restructured everything so I can swap models in minutes. I replaced my claude.md with agents.md. I use harnesses like OpenCode or Pi. Nothing in my stack assumes a specific vendor.

If your whole workflow breaks because one company changes their terms, you don't have a foundation. You have a dependency.

Open source is the only version of this future where you actually stay in control.

## Everyone is talking about Agentic AI. Most people are confusing it with something else

Everyone is talking about Agentic AI. Most people are confusing it with something else.

Here's what it actually is, and what it's not:

❌ These are NOT Agentic AI:

🔺 LLM Chatbots:
You ask. It answers. That's it.

Query goes in → System prompt → LLM processes → Output comes out No memory.

No planning. No autonomy. Reactive by design. Not agentic.

🔺 RPA (Robotic Process Automation):
It executes scripts. It doesn't think.

Query triggers a script → Fixed rules execute → Output comes out It follows what it was programmed to do.

Change the environment and it breaks. No reasoning involved.

🔺 Simple RAG:
Smarter answers, but still not agentic.

Query gets embedded → searches knowledge base, vector DB, web data → augments LLM context → Output comes out Better retrieval.

Still just answering questions. No planning. No action. No autonomy.

✅ This IS Agentic AI:

A true agentic system doesn't just respond. It plans, remembers, acts, and adapts, on its own.

→ Memory: knows what happened before and builds on it
→ Planning: breaks complex tasks into steps before acting
→ Tools: takes real actions in the world, not just generates text
→ Feedback loops: reflects, adjusts, and improves mid-task
→ Human-in-the-loop: escalates when it needs to
→ Multi-agent coordination via MCP + A2A Protocol:

▪️ Coding Agent → writes and executes code (LangChain)
▪️ Retrieval Agent → finds and pulls relevant information (LlamaIndex)
▪️ Citation Agent → sources and verifies claims (CrewAI)

The orchestrator delegates. The agents specialize. The system adapts.
That's Agentic AI.

## 6 Clean code rules

(Start these now):

1 Separation of Concerns (SOC):

☑ Break down a complex program into smaller units.
☑ Each unit should focus on a specific task.

===

2 Document Your Code (DYC):

☑ Write code for your future self and others.
☑ Explain complex code sections with comments and documentation.

===

3 Don't Repeat Yourself (DRY):

☑ Don't waste time writing the same code again.
☑ Instead use functions, modules, and existing libraries.

===

4 Keep It Simple, Stupid (KISS):

☑ Simple is hard, but better.
☑ Readable code > clever code.

===

5 Test Driven Development (TDD):

☑ Write a failing test first.
☑ Write code to make the test pass.
☑ Then clean up the code without changing behaviour.

===

6 You Ain't Gonna Need It (YAGNI):

☑ Build only essential features.
☑ Don't build features you think you might need later.

===

The bottom line:
☑ Leave the codebase cleaner than you found it.
