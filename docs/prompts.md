Prompts given to Claude Code: 

In @docs/CLAUDE.md, read the file and familiarize yourself with the project, specs, stack and rules. 
If you have any questions or clarifications, ask me. 

-----------------------------------------------------------

This is meant to be a fresh project. I was working on an initial 
planning stage beforehand, your job is to just extract 
what I want to accomplish in the CLAUDE.md file and adhere to it. Ignore the prompts.md file, this is bookkeeping meant 
for myself only. 

Question answers: 
1. Still escalate the query and flag it for staff but do not 
do anything else, just tell the user that the staff has been notified 
2. The parent is notified that staff was informed because of 
either thing: the answer was deemed unanswerable by the system or it was escalated. The operator is able to independently 
then use that log to make a decision on what to do (resolve the question or add answer to knowledge base). Since the user's part 
is just asking questions, we don't have to worry about getting 
the answer BACK to the user, instead update the KB
3. Yes, come up with a mock handbook including common information listed. 
4. This will be hosted on Render, I will figure out if I want to 
use the free tier or purchase a cheap plan to persist SQLite logs if redployed or restarted. List this as a design decision/tradeoff in decision_logs.md to keep track of it. For now, I will use Render's free plan for demoing and confirm if it is viable. 
5. I will update the .env to include this information. 
6. I am making another design decision here, I want to use React 
since I am most comfortable with it instead. This is a design 
choice I am making since I am not really a frontend dev, so I 
will use the framework that makes the most sense to me instead 
of starting with something new. 

--------------------------------------------------------------

Start with the handbook logs, create mock data. 

--------------------------------------------------------------

Next I want you to create @docs/architecture.md where you will 
include the structure of the files as well as what will 
go in them. I want you to do this before starting any other 
code. Then I will review what you put in there to make sure 
that there isn't any grey area. 
--------------------------------------------------------------
Ok great, now I want you to write the file structure without 
any code, just implement the folders, whatever we are intending 
to implement. 
--------------------------------------------------------------
Ok now I want you to implement the front-end. Go to @docs/plans/frontend.md, read that plan and compare it to our specs and CLAUDE.md and architecture.md, if there are no conflicts, proceed to starting the build, otherwise come back to me with any questions or design choices that need tailoring. Remember to update decision logs. 

--------------------------------------------------------------
we can safely ignore staff follow-ups as that is not within the 
scope nor is that feasible in the time-frame, let's just give 
the staff an option to add an answer for it to the knowledge
base and resolve the question, or to just leave it be. 

---------------------------------------------------------------

Ok great, the mock frontend works, now we can plug in the backend, starting with the @plans/backend.md
---------------------------------------------------------------

For sensitivity, always send to staff since it's better to have 
false positives in this situation rather than false negatives. 
Update this decision choice. 

---------------------------------------------------------------
You are getting confused here, simply if something is marked as
sensitive, it will always be escalated. We do not need a "0.90" 
score to escalate it. We can lower the threshold to around 0.70 so that we can pool in more questions and avoid the false negative claims. 

---------------------------------------------------------------
Proceed with the backend plan, just like the frontend, check 
to see if there are any disparities between any design decisions
or anything needing a second look. 

---------------------------------------------------------------
Is this file only for testing which Gemini model we should use? 
If so, then we can use this during the testing stage. 

---------------------------------------------------------------
Rename @app to @backend so that it's easier to differentiate. 
I want this to be readable for any engineer to look back at and navigate. 

---------------------------------------------------------------
Make sure every time we update a piece of the backend, that we 
also make sure it works via testing. Things like adherence, pipeline, triage and urgency are things that need separate component testing. 

---------------------------------------------------------------
explain the chunking logic with upsert_chunk in kb.py
ans: upsert_chunk writes a row (from db.py), which is where 
db extracts new entries from the staff updates
--------------------------------------------------------------
SIDE NOTE FOR DEVELOPMENT: 

steps in building backend: 
build data layer + test 
build retrieval + sensitivity + generation + test
build pipeline + test
build api routes + main + test 
---------------------------------------------------------------
Note on TOP_K in retrieval.py, what TOP_K value are we using and why? Since I want this to be as accurate as possible, we should 
use a smaller TOP_K value. 

result: changed 3 -> 2 to prevent inaccuracies, better because more accurate but gives more context than just using 1. 

---------------------------------------------------------------
Now that we are testing the actual Gemini API, make sure to bring back the small model testing file so that we can determine 
which one gives what we want. 
---------------------------------------------------------------
Calibration leads to floor being 0.50 where completely irrelevant questions sat at around 0.50. Using gemini-3.5-flash-list as our Gemini model. 
---------------------------------------------------------------
SIDE NOTE: 

I tweaked CLAUDE.md so that every time an endpoint is being tested by Claude as a "smoke-screen", it kills the process to avoid collision between me testing and Claude testing. 
----------------------------------------------------------------
1. Yes, number checking is important in the context of producing responses. Things like $6 and 10:00 AM are factual answers that require high confidence. This is an important fix to make to avoid hard details that parents would remember or act on. 

2. Telling the model to write the numbers as digits is the better option because it feels more organic than just creating stricter retrieval bounds. 
-----------------------------------------------------------------
