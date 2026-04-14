---
campaign_name: "Canary Test Campaign"
campaign_slug: "canary_test"
schedule_id: 50
drip_days:
  - 2026-04-21
  - 2026-04-22
  - 2026-04-23
tag_template: "canary-test-{role}"
sleep_seconds_min: 60
sleep_seconds_max: 180
step_intervals_days: [0, 5, 6, 7, 8]
---

## variant: admin
target_role_label: "Superintendent / Principal"
num_steps: 5

### Step 1 — Subject: Quick note on your CS rollout at {{company}}
Hi {{first_name}},

Dropping a quick note on something we've been rolling out for district admin teams in {{state}}. It's a turn-key CS curriculum that works across grade levels, and the early results have been encouraging.

Worth sending over a one-page overview on how this works for districts your size?

Steven

### Step 2 — Subject: Re: Quick note on your CS rollout at {{company}}
Hey {{first_name}},

Following up. Wanted to mention we can spin up free trial licenses for any of your teachers to pilot with, no strings attached.

Happy to send more info if useful. More at <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

Steven

### Step 3 — Subject: 15 minutes next week?
Hi {{first_name}},

Third try here. If this resonates at all, <a href="https://hello.codecombat.com/c/steven/t/130">grab 15 min here</a> and I'll walk you through what it looks like for a district your size.

No pitch. Just a quick look.

Steven

### Step 4 — Subject: Data from Bobby Duke Middle School
{{first_name}},

One more note. Happy to share the data from Bobby Duke Middle School, one of our strongest case studies. They saw measurable gains across grade levels over a full year.

More context at <a href="https://www.codecombat.com/schools">codecombat.com/schools</a> if useful.

Steven

### Step 5 — Subject: Should I close the loop?
{{first_name}},

Last note from me. If there's a better person on your team for this conversation, happy to start there instead. Otherwise I'll close the loop and circle back next term.

If you'd rather just chat, <a href="https://hello.codecombat.com/c/steven/t/130">grab 15 min here</a>.

Steven

## variant: teacher
target_role_label: "CS Teacher / Math Teacher"
num_steps: 5

### Step 1 — Subject: Your CS classroom at {{company}}
Hi {{first_name}},

I work with CS teachers across {{state}} and wanted to drop a quick note. We built a turn-key curriculum that looks and feels like a video game but has real rigor underneath, and the kids actually want to do it.

Want me to send over the highlights?

Steven

### Step 2 — Subject: Re: Your CS classroom at {{company}}
{{first_name}},

Following up. We can set up free trial licenses for your class anytime, no strings. Teachers tell us the hardest part is usually getting admin buy-in, and this helps make that case.

More at <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

Steven

### Step 3 — Subject: 15 min to see it in action?
{{first_name}},

Third note. If you want to see what it looks like in the classroom, <a href="https://hello.codecombat.com/c/steven/t/130">grab 15 min here</a> and I'll show you live.

Steven

### Step 4 — Subject: What students say
Hi {{first_name}},

One more. The thing teachers love most is that students actually ask to keep playing when the bell rings. Bobby Duke Middle School is one of our strongest case studies, and I'm happy to share what they saw.

More at <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

Steven

### Step 5 — Subject: Closing the loop
{{first_name}},

Final note from me. If this isn't a fit, no worries, I'll close the loop. If it is, <a href="https://hello.codecombat.com/c/steven/t/130">grab 15 min here</a> whenever works.

Steven

## variant: it
target_role_label: "Director of Technology / EdTech Coordinator"
num_steps: 5

### Step 1 — Subject: CS rollout that won't blow up your stack
Hi {{first_name}},

Know you're busy so I'll keep this short. We built a browser-based CS curriculum that runs on Chromebooks without any install, no LMS integration needed, and has single-sign-on options if you already use Clever or ClassLink.

Worth a quick overview?

Steven

### Step 2 — Subject: Re: CS rollout that won't blow up your stack
{{first_name}},

Following up. For EdTech teams, the big win is that teachers can stand this up without an IT ticket for every class. No new infrastructure to manage. More at <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

Steven

### Step 3 — Subject: 15 minutes to walk the stack?
{{first_name}},

Third try. If any of this sounds relevant, <a href="https://hello.codecombat.com/c/steven/t/130">grab 15 min here</a> and I'll walk you through the technical side: auth, data privacy, rostering, the whole picture.

Steven

### Step 4 — Subject: Data privacy + rostering
Hi {{first_name}},

One more note. We're SOC 2 compliant, COPPA aligned, and integrate with Clever/ClassLink for rostering. Happy to send over the data processing agreement if your team needs to review it.

More at <a href="https://www.codecombat.com/schools">codecombat.com/schools</a>.

Steven

### Step 5 — Subject: Pointing at the right person?
{{first_name}},

Last note. If EdTech isn't where this conversation belongs, happy to start with whoever owns CS curriculum. Otherwise, <a href="https://hello.codecombat.com/c/steven/t/130">grab 15 min here</a> whenever works.

Steven
