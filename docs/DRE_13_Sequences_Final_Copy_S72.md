# DRE Campaign — 13 Sequences, Final Copy

**Session 72, 2026-04-16** — Handoff to Claude Code for Outreach build.

Derivation reasoning lives in `DRE_Sequence_Family_Derivation_S72.md`. This file is copy only, ready to build.

---

## Build order

Ship in this order. INT-Universal first as safety net, TC-Universal-Residual second to lock copy voice on the biggest cohort, then TC grade splits, then specialty variants.

| Order | Sequence | Leads (measured) |
|---|---|---:|
| 1 | INT-Universal | 867 |
| 2 | TC-Universal-Residual | 6,957 |
| 3 | TC-MS | 5,452 |
| 4 | TC-HS | 4,892 |
| 5 | TC-Elem | 4,941 |
| 6 | TC-Virtual | 441 |
| 7 | TC-District | 442 |
| 8 | TC-All-Grades | 126 |
| 9 | LIB | 633 |
| 10 | LQD-Universal | 407 |
| 11 | INT-Teacher | 404 |
| 12 | TC-Teacher | 393 |
| 13 | IT-ReEngage | 182 |

**Total:** 13 sequences, 26,137 measured eligible leads.

---

## Build spec (applies to all 13)

- **Mailbox:** 11 (Steven)
- **Schedule:** 52 "Admin Mon-Thurs Multi-Window" OR 53 "Teacher Tue-Thu" depending on cohort composition
- **Intervals:** 0 / 5 / 5 / 5 / 5 / 5 days
- **Owner:** Steven (ID 11)
- **Tags:** `dre-2026-spring`, plus sequence-specific tag (e.g. `dre-tc-ms`, `dre-lib`)
- **State:** create disabled (Rule 15)
- **Step 2 across all 13:** Outreach template 43784 ("CodeCombat's Comprehensive K-12 Suite") — reference the template directly, do not rewrite
- **Meeting link (all Step 5s):** `https://hello.codecombat.com/c/steven/t/131`
- **Merge fields:** `{{first_name}}`, `{{company}}`, `{{state}}` — verify population before activation

### Banned phrases (enforced across all 13)

No em dashes. No "circling back," "touch base," "just checking in," "reach out," "I'd love to," "hop on a call," "quick follow up," "one more angle," "I'm Steven," "I dropped the ball."

### Links in Outreach

Plain URLs shown in this doc for readability. When created in Outreach via the API, wrap as HTML anchor tags for click-tracking.

---

# 1. TC-Universal-Residual (6,957) — THE BASELINE

*Unknown role, unknown grade. Universal voice. Reference for all other TC variants.*

## Step 1 — Interval 0
**Subject:** the game thing

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. No hard feelings.

One thing worth knowing before you write us off for good: students play it thinking it's a video game. They're writing real Python by week three and most don't clock that they're learning to code.

Want to see a fresh demo, or get a quote in hand so you've got something real for fall budget conversations?

Steven

## Step 2 — Interval 5
**Template:** 43784 (CodeCombat's Comprehensive K-12 Suite)

## Step 3 — Interval 5
**Subject:** 850,000 lines

{{first_name}},

A number I keep coming back to: the average CodeCombat student writes 850,000+ lines of real code over their time in the platform. Not drag-and-drop blocks. Actual Python and JavaScript.

That only happens because kids want to keep playing. Teachers get zero-prep slides, CSTA and ISTE alignment, and a dashboard that takes five minutes to learn. No CS background needed.

Happy to spin up free trial licenses so you can see it in action. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most {{state}} schools I work with are locking in fall curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is on the list for next year at {{company}}, this is the window to get a quote in hand so you have something real to bring to those internal conversations.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one. CodeCombat runs the only educational coding esports in the world. It's async, zero chat, and runs on the Chromebooks you already have. No $1K gaming rigs.

The kids who show up for this usually aren't the kids who show up for anything else. That's the part that matters. Schools use it to pull students into CS who wouldn't otherwise touch it.

Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar if you want to see how it works: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Every district is writing policy right now, most of them without a curriculum in place.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 2. TC-MS (5,452) — Middle school confidence

*Sweet spot audience. Voice most confident here.*

## Step 1 — Interval 0
**Subject:** middle schoolers and code

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note.

Middle school is where coding either clicks or doesn't, and most platforms lose kids right here. CodeCombat flips it: students open a video game, type real Python to move their character, and stay locked in because the gameplay demands it. By week three they're writing actual code without thinking of it as coding.

Want a fresh demo, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** why it sticks at MS

{{first_name}},

The middle school problem is attention. You have a 42-minute period, half the kids are pre-coders, half are already bored, and block-based tools feel babyish to 7th graders.

CodeCombat solves this by looking like a game they'd actually play at home. Average student writes 850,000+ lines of real Python and JavaScript over time in the platform. Teachers get zero-prep slides and CSTA-aligned lesson plans. No CS background needed.

Happy to set up free trial licenses for a couple of your classes. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most {{state}} middle schools I work with are locking in fall curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is on the list for next year at {{company}}, this is the window to get a quote in hand so you have something real to bring to those internal conversations.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one. CodeCombat runs the only educational coding esports in the world. Middle school is actually our strongest bracket — kids this age want to compete at something that isn't sports.

Async, zero chat, runs on your existing Chromebooks. No $1K gaming rigs. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar if you want to see how it works: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Every district is writing policy right now, most of them without a curriculum in place.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 3. TC-HS (4,892) — Outcomes and rigor

*AP, CTE, transcripts, college prep. Serious voice.*

## Step 1 — Interval 0
**Subject:** real Python, high school level

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note before I stop.

High school CS has an engagement problem that most platforms make worse, not better. CodeCombat runs students through real Python and JavaScript inside a game they actually want to play, which means they stick with it long enough to build something that matters on a transcript.

Want a fresh demo, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** AP CSP and beyond

{{first_name}},

Students on CodeCombat write 850,000+ lines of real code over their time in the platform. Not blocks. Real Python and JavaScript, text-based from day one.

That matters for high school because it means your AP CSP kids are actually prepared, your CTE pathways have something real to anchor to, and students who want to take CS further have a foundation that translates. CSTA and ISTE aligned, AP CSP framework-compatible.

Happy to spin up trial licenses for a class or two. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most {{state}} high schools I work with are locking in fall CS curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is on the list for next year at {{company}} — whether that's a new AP CSP section, a CTE expansion, or just a better intro-to-coding class — this is the window to get a quote in hand.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one. CodeCombat runs the only educational coding esports in the world. For high schools this usually shows up as an after-school club or CTE enrichment.

Async, zero chat, runs on your existing Chromebooks. Global AI League has $1K scholarships per age bracket — college-application-worthy for the kids who place.

15 minutes on my calendar if you want to see how it works: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Every district is writing policy right now, most of them without a curriculum in place.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 4. TC-Elem (4,941) — Young learners

*K-5. CodeCombat Jr. Different proof points.*

## Step 1 — Interval 0
**Subject:** kids reading code before chapter books

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note.

Elementary CS is hard because most tools assume readers. CodeCombat Jr. handles K-2 with visual-first programming, and full CodeCombat takes over by 3rd grade with real Python. Kids who can barely read chapter books end up writing actual code because the game makes them want to.

Want a fresh demo, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** K-5 without a CS teacher

{{first_name}},

The elementary CS problem: you probably don't have a CS specialist. Classroom teachers run CS alongside everything else, which means any platform has to be runnable with zero prep.

CodeCombat Jr. and CodeCombat were built for that. Zero-prep lesson slides, 5-minute teacher dashboard, CSTA and ISTE alignment, runs on whatever devices you have. Students across grade bands write 850,000+ lines of real code on average.

Happy to spin up trial licenses for a classroom or two. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most {{state}} elementary schools I work with are locking in fall curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is going to be more than an occasional Hour of Code event at {{company}} next year, this is the window to get a quote in hand so you have something real to bring to those conversations.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** CS clubs and enrichment

{{first_name}},

Quick one. A lot of elementary schools use CodeCombat for after-school CS clubs, gifted enrichment, or rotation-block coding time.

Runs on Chromebooks or iPads, kids can go at their own pace, and there's an esports side for older elementary kids who want to compete. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar if you want to see how it works: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Every district is writing policy right now, most of them without a curriculum in place.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 5. INT-Universal (867) — Warm re-engage

*Event context. Warmer tone than TC.*

## Step 1 — Interval 0
**Subject:** we crossed paths

Hi {{first_name}},

We crossed paths a while back — conference, webinar, maybe Hour of Code season. Things got quiet after that.

Worth one more note before I stop. The short version of CodeCombat: students open it thinking it's a video game, write real Python by week three, and most don't clock they're learning to code. Teachers run it without a CS background.

Want a fresh look, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** 850,000 lines

{{first_name}},

A number worth sharing since we already have a thread: the average CodeCombat student writes 850,000+ lines of real code over their time in the platform. Not blocks. Real Python and JavaScript.

Kids keep coming back because the gameplay demands it. Teachers get zero-prep slides, CSTA and ISTE alignment, and a dashboard that takes five minutes to learn.

Happy to spin up trial licenses so you can see it in action. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Since we'd already connected once, figured I'd flag the timing.

Most {{state}} schools I work with are locking in fall curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is on the list for next year at {{company}}, this is the window to get a quote in hand. Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one you might not have caught when we first talked. CodeCombat runs the only educational coding esports in the world. Async, zero chat, runs on your existing Chromebooks.

The kids who show up for this usually aren't the kids who show up for anything else. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Every district is writing policy right now, most of them without a curriculum in place.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 6. LIB (633) — Self-paced, library use case

*Self-paced student use. Librarian-run clubs. Different implementation model.*

## Step 1 — Interval 0
**Subject:** self-paced coding at the library

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note.

Most librarians don't want to run a coding class. What works at the library is a self-paced platform students can drop into during open lab time, study hall, or a coding club — and actually stay engaged with. CodeCombat is built for that. Kids play a video game, write real Python to move their character, and run themselves.

Want a fresh demo, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** coding clubs that run themselves

{{first_name}},

The thing librarians tell me: they want to offer coding but don't want to become the coding teacher.

CodeCombat handles that. Students log in, the game teaches them, you don't need to explain Python syntax. Average student writes 850,000+ lines of real code over their time in the platform. Works for drop-in library time, after-school clubs, or classes where you're supporting a teacher.

Happy to spin up trial licenses so you can see how it runs. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Library budgets at most schools I work with are getting locked in right now for fall. Leftover end-of-year funds often work for a pilot too.

If coding is something you want to offer more seriously at {{company}} next year, this is the window to get a quote in hand so you have something real to bring to the conversation with admin.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** coding esports for after-school

{{first_name}},

Quick one. A lot of librarians run CodeCombat's esports side as an after-school club — async, zero chat, runs on existing Chromebooks.

It's the only educational coding esports in the world, and the Global AI League has $1K scholarships per age bracket. Perfect fit if you're looking for something structured to build an after-school program around.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Every district is writing policy right now, most of them without a curriculum in place. Libraries often end up being the place where this gets figured out first.

If this isn't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If it is and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 7. TC-District (442) — Buyer persona

*Restructured. Policy forward. Budget stronger. Game hook dropped.*

## Step 1 — Interval 0
**Subject:** CS policy at {{company}}

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note now that the landscape has shifted.

States are moving fast on CS and AI mandates. California passed AB 2097. Ohio's AI policy mandate hits this summer. Most districts I talk to are writing policy without a curriculum in place to back it up. CodeCombat covers K-12 CS and AI literacy in one platform, aligned to CSTA and state standards.

Want a fresh demo, or a quote in hand for fall budget conversations?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** one platform, K-12

{{first_name}},

The problem most districts hit with CS: elementary uses one tool, middle school uses another, high school uses a third, and no one has visibility across the pipeline.

CodeCombat runs K-12 in one platform. Elementary uses CodeCombat Jr. with visual-first programming. 3rd-12th writes real Python and JavaScript. Same dashboard, same account structure, same data. Students across the district write 850,000+ lines of real code on average.

Replaces the Scratch + Code.org + Replit patchwork most districts are running now.

Happy to scope what this looks like at {{company}} scale. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most {{state}} districts I work with are locking in fall curriculum right now. April and May is when the real decisions get made, even though POs don't drop until summer.

If CS is part of the conversation at {{company}} for next year, this is the window to get district-level pricing in hand so you have something real for board conversations.

Leftover end-of-year funds also work for a pilot at a few schools.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** district-wide coding esports

{{first_name}},

Quick one. Districts are increasingly using CodeCombat's esports side as a district-wide initiative — schools compete against each other internally, top teams go to the Global AI League.

Async, zero chat, runs on existing Chromebooks. Works as a way to build CS culture across the whole district without every school needing its own CS teacher.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

If CS and AI aren't a priority at {{company}} this cycle, I'll stop taking up space in your inbox. If they are and I'm the wrong person to be talking to — curriculum director, CTO, superintendent — send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 8. TC-Virtual (441) — Cyber charter / online academies

*Built-for-remote as real differentiation.*

## Step 1 — Interval 0
**Subject:** built for async from day one

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note.

Most CS curriculum was built for a classroom and retrofitted for remote. CodeCombat was built the other way around — async from day one, students self-pace through a video game that teaches them real Python. Which means for a cyber school or online academy, there's no "does this work remotely" question. The whole thing is remote-native.

Want a fresh demo, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** async engagement at {{company}}

{{first_name}},

The hard problem for online schools is engagement. Kids drop off async work constantly. CodeCombat is one of the only CS platforms where students stay locked in without a teacher prompting them, because the gameplay is the hook.

Average student writes 850,000+ lines of real Python and JavaScript over time in the platform. Teachers get dashboards that show exact progress per student — critical when you can't walk the room.

Happy to spin up trial licenses for a cohort. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Online schools I work with tend to lock in fall curriculum earlier than brick-and-mortar — April and May is the real decision window.

If CS is on the list for next year at {{company}}, this is the time to get a quote in hand. Leftover end-of-year funds also work for a pilot cohort.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** coding esports for online schools

{{first_name}},

Quick one. CodeCombat runs the only educational coding esports in the world, which is interesting for online schools specifically because it's already async-native and gives students something structured to compete in without needing a physical venue.

Zero chat, runs on whatever devices students already have. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real. Cyber schools and online academies tend to be ahead of brick-and-mortar on this, but the policy expectations are the same.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 9. TC-All-Grades (126) — One-platform pitch

*Single-campus K-12 schools. "One platform" is the entire hook.*

## Step 1 — Interval 0
**Subject:** one platform, 5 through 18

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note.

{{company}} is a K-12 school, which means you're probably running three different CS tools for three different age bands. CodeCombat is one platform that covers the full range — CodeCombat Jr. for your youngest kids, full CodeCombat with real Python by 3rd grade, all the way through high school. Same dashboard, same account structure.

Want a fresh demo, or a quote in hand for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** kindergarten to graduation

{{first_name}},

The thing K-12 schools tell me: nobody makes a single platform that actually works for 5-year-olds AND 17-year-olds. Which means teachers end up duct-taping together Scratch + Code.org + Replit + whatever the high school CS teacher prefers.

CodeCombat spans the whole range. Visual-first for K-2, real Python for 3-12. Average student writes 850,000+ lines of real code over time in the platform. One contract, one onboarding, one dashboard.

Happy to spin up trial licenses across grade bands. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most K-12 schools I work with are locking in fall curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is on the list for next year at {{company}}, this is the window to get a quote in hand. One-platform pricing usually comes in lower than whatever patchwork you're running now.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one. CodeCombat runs the only educational coding esports in the world. For a K-12 school, the fun part is you can run age-appropriate brackets across your whole campus in one program.

Async, zero chat, runs on existing Chromebooks. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 10. LQD-Universal (407) — Picked up where it stalled

*Warmest pool. They asked for something. Don't pretend they just "looked."*

## Step 1 — Interval 0
**Subject:** picking up where we left off

Hi {{first_name}},

You asked about CodeCombat licensing (or a quote, or a demo) a while back and something got in the way. Happens.

Happy to pick it up wherever it stalled. Timing, pricing, approval holdup, different decision-maker — whatever stopped it, I can probably work around.

Want me to just send a fresh quote based on what you were originally looking at, or start over with what your current need looks like?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** what changed since then

{{first_name}},

A few things worth knowing since we last talked:

CodeCombat now covers AI literacy curriculum alongside core CS. Esports has expanded into a full Global AI League with $1K scholarships. Platform is fully Chromebook-optimized. And state CS/AI mandates have moved fast — CA passed AB 2097, OH's AI policy deadline hits this summer.

Average student still writes 850,000+ lines of real Python and JavaScript over time in the platform. Core product is stronger than ever.

Happy to run you a fresh quote. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Given we already had a thread going, wanted to flag the timing.

Most {{state}} schools I work with are locking in fall curriculum right now. April and May is when the real decisions get made. If the original budget conversation at {{company}} stalled out, this is a natural window to restart it.

Leftover end-of-year funds also work if you want to pilot before committing.

Want me to put fresh numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one you may not have caught when we first talked. CodeCombat runs the only educational coding esports in the world. Async, zero chat, runs on existing Chromebooks.

If engagement or "will students actually use this" was part of what stalled the original conversation, esports is the answer. Kids who wouldn't touch CS otherwise show up for competition.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

If CodeCombat isn't the right fit for {{company}} anymore, no worries. If it still is and I'm the wrong person to be talking to, send me the right one and I'll take it from there.

States are moving fast on CS and AI policy right now — CA's AB 2097, Ohio's summer AI mandate, the federal AI literacy executive order. If that changes the picture, happy to pick this back up.

Good luck with the rest of the year.

Steven

---

# 11. INT-Teacher (404) — Warm + teacher-specific

*Event context + teacher voice.*

## Step 1 — Interval 0
**Subject:** we crossed paths

Hi {{first_name}},

We crossed paths a while back — conference, webinar, maybe Hour of Code season. Things got quiet.

One more note before I stop. If CodeCombat is still somewhere on your radar for {{company}}: students open it thinking it's a video game, type real Python to move their character, and most don't clock they're learning to code. No CS background needed on the teacher side.

Want a fresh demo, or a quote for fall?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** what your students actually see

{{first_name}},

Since we already have a thread, here's the thing most teachers tell me clicks:

Students open CodeCombat and see a video game. They write real code to move their character. Most don't realize they're learning CS until weeks in. Meanwhile you get zero-prep lesson slides, CSTA and ISTE alignment, and a dashboard that takes five minutes to learn.

850,000+ lines of real code per student on average.

Want me to set up free trial licenses for your classes?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Flagging the timing since we'd connected before.

Most {{state}} schools are locking in fall curriculum right now. April and May is when the real decisions happen. If CS is on the list for next year at {{company}}, this is the window.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one you may not have caught when we first talked. CodeCombat runs the only educational coding esports in the world. Async, zero chat, runs on existing Chromebooks.

Teachers use it to pull students into CS who wouldn't otherwise touch it. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 12. TC-Teacher (393) — Populated-title teachers

*Close to baseline. Slight peer-to-peer tightening.*

## Step 1 — Interval 0
**Subject:** the game thing

Hi {{first_name}},

You signed up for CodeCombat a while back and it went quiet. No hard feelings.

One thing worth knowing before you write us off: students play it thinking it's a video game. They're writing real Python by week three and most don't clock that they're learning to code. Teacher-side is zero-prep — you don't need a CS background.

Want to see a fresh demo, or get a quote in hand so you've got something real for fall budget conversations?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** 850,000 lines

{{first_name}},

A number I keep coming back to: the average CodeCombat student writes 850,000+ lines of real code over their time in the platform. Not drag-and-drop blocks. Actual Python and JavaScript.

That only happens because kids want to keep playing. You get zero-prep slides, CSTA and ISTE alignment, and a dashboard that takes five minutes to learn.

Happy to set up free trial licenses for a couple of your classes. Want me to?

Steven

## Step 4 — Interval 5
**Subject:** fall budget at {{company}}

{{first_name}},

Most {{state}} schools I work with are locking in fall curriculum right now. April and May are when the decisions actually get made, even though the POs don't drop until summer.

If CS is on the list for next year at {{company}}, this is the window to get a quote in hand so you have something real to bring to those internal conversations.

Leftover end-of-year funds also work for a pilot.

Want me to put numbers together?

Steven

## Step 5 — Interval 5
**Subject:** Chromebook esports

{{first_name}},

Quick one. CodeCombat runs the only educational coding esports in the world. Async, zero chat, runs on the Chromebooks you already have.

The kids who show up for this usually aren't the kids who show up for anything else. Global AI League has $1K scholarships per age bracket.

15 minutes on my calendar: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming before I go: states across the country just turned a corner on CS and AI in K-12. California passed AB 2097. Ohio's AI policy mandate hits this summer. The federal AI literacy executive order is real.

If CS and AI aren't on the {{company}} roadmap this year, I'll stop taking up space in your inbox. If they are and I'm the wrong person to talk to, send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

# 13. IT-ReEngage (182) — IT persona rewrite

*Game hook dropped. Chromebook deployment, SSO, FERPA, COPPA. Buyer not user.*

## Step 1 — Interval 0
**Subject:** CodeCombat on your Chromebook fleet

Hi {{first_name}},

You looked at CodeCombat a while back and it went quiet. Worth one more note to the right audience.

Most CS curriculum is an IT headache — Java installs, local runtimes, non-Chromebook-friendly, weird SSO, vague FERPA docs. CodeCombat runs fully in-browser on any Chromebook, supports Clever and ClassLink SSO, and has clean FERPA/COPPA documentation. No local installs, no student PII going to third parties.

Want to review the data-handling docs, or a scoped pilot on one OU?

Steven

## Step 2 — Interval 5
**Template:** 43784

## Step 3 — Interval 5
**Subject:** deployment details

{{first_name}},

For the IT side specifically:

- Runs in-browser, no installs, no Java, no local runtime
- Clever and ClassLink SSO, Google Classroom rostering
- FERPA and COPPA compliant, SOC 2 Type II
- Admin dashboard with district-level visibility and student data controls
- Works on any Chromebook spec — no GPU or memory floor

If you want the full data handling / privacy / security package, I can send it over. Most IT teams clear CodeCombat faster than the CS curriculum sitting next to it in the review queue.

Want me to send the docs?

Steven

## Step 4 — Interval 5
**Subject:** fall rollout at {{company}}

{{first_name}},

Most districts I work with are finalizing fall deployments right now. If CS curriculum is going to be part of the {{company}} rollout — whether that's a new platform or replacing the current patchwork — this is the window to get it into the IT review queue early.

Happy to get docs and pricing to the curriculum side in parallel if useful.

Want me to start the paperwork on your end?

Steven

## Step 5 — Interval 5
**Subject:** pilot OU?

{{first_name}},

Quick one. If a full rollout is too much to commit to right now, a scoped pilot on one OU usually takes about 20 minutes to stand up. Clever or ClassLink SSO, one building, a few classes, we see how it handles in your actual environment.

Lower risk than a full procurement cycle, gives curriculum something real to evaluate against, gives you a production-environment test of the platform.

15 minutes on my calendar if you want to scope it: https://hello.codecombat.com/c/steven/t/131

Steven

## Step 6 — Interval 5
**Subject:** wrong person?

{{first_name}},

Last one from me, promise.

Worth naming: states across the country just passed CS and AI mandates that are going to land on IT in the next 12-18 months. CA's AB 2097, Ohio's AI policy mandate, the federal AI literacy executive order. Procurement, data privacy review, SSO integration — all of it is about to hit the queue.

If CodeCombat isn't on the {{company}} radar for next year, I'll stop taking up space in your inbox. If it is and I'm the wrong person to talk to — curriculum, CTO, or whoever owns CS procurement — send me the right one and I'll take it from there.

Good luck with the rest of the year.

Steven

---

## Pre-activation checklist (for Claude Code)

Before activating any sequence in Outreach:

1. Create all 13 disabled (Rule 15)
2. Verify `{{first_name}}`, `{{company}}`, `{{state}}` populate cleanly across the cohort
3. Confirm template 43784 renders correctly as Step 2 (HTML preserved, links tracked)
4. Confirm meeting link `https://hello.codecombat.com/c/steven/t/131` is wrapped as trackable anchor tag in all Step 5s
5. Apply sequence-specific tags (`dre-2026-spring` + cohort tag)
6. Confirm schedule assignment (52 admin-heavy vs 53 teacher-heavy per cohort)
7. Load order follows build order above — INT-Universal first as safety net, TC-Universal-Residual second for copy validation on biggest cohort
8. Stagger activation: activate #1 and #2, let them run 3-5 days, review open/reply signal before activating #3-#13
