/**
 * Code.gs — Scout GAS Bridge
 * 
 * This is your private API that lives inside Google Apps Script.
 * It runs as YOU, with full access to your Gmail, Calendar, and Slides.
 * Deploy as a Web App (execute as Me, access to Anyone) and protect
 * with the secret token below.
 * 
 * HOW TO DEPLOY:
 * 1. Go to script.google.com → New Project → name it "Scout Bridge"
 * 2. Paste this entire file into the editor (replace the default code)
 * 3. Change SECRET_TOKEN below to any long random string you make up
 * 4. Click Deploy → New Deployment → Web App
 *    - Execute as: Me (steven@codecombat.com)
 *    - Who has access: Anyone
 * 5. Click Deploy → copy the Web App URL
 * 6. Set GAS_WEBHOOK_URL = that URL in Railway
 * 7. Set GAS_SECRET_TOKEN = your chosen token in Railway
 */

// ─── CHANGE THIS — make it a long random string ───────────────────────────────
var SECRET_TOKEN = "REPLACE_WITH_YOUR_SECRET_TOKEN_HERE";
// ─────────────────────────────────────────────────────────────────────────────


/**
 * Entry point for all POST requests from Scout.
 * Expects JSON body: { token, action, params }
 */
function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);

    // Auth check
    if (payload.token !== SECRET_TOKEN) {
      return jsonResponse({ success: false, error: "Unauthorized" }, 401);
    }

    var action = payload.action;
    var params = payload.params || {};

    // Route to the right handler
    switch (action) {

      // ── Gmail ──────────────────────────────────────────────────
      case "get_sent_emails":
        return jsonResponse(getSentEmails(params));

      case "create_draft":
        return jsonResponse(createDraft(params));

      case "search_inbox":
        return jsonResponse(searchInbox(params));

      // ── Calendar ───────────────────────────────────────────────
      case "get_calendar_events":
        return jsonResponse(getCalendarEvents(params));

      case "create_calendar_event":
        return jsonResponse(createCalendarEvent(params));

      case "log_call":
        return jsonResponse(logCall(params));

      // ── Slides ─────────────────────────────────────────────────
      case "create_presentation":
        return jsonResponse(createPresentation(params));

      case "create_district_deck":
        return jsonResponse(createDistrictDeck(params));

      // ── Health check ───────────────────────────────────────────
      case "ping":
        return jsonResponse({ success: true, message: "Scout Bridge is live", user: "steven@codecombat.com" });

      // ── Phase 5: Google Docs ────────────────────────────────────
      case "createGoogleDoc":
        return jsonResponse(createGoogleDoc(params));

      default:
        return jsonResponse({ success: false, error: "Unknown action: " + action });
    }

  } catch (err) {
    return jsonResponse({ success: false, error: err.toString() });
  }
}


// ════════════════════════════════════════════════════════════
// GMAIL FUNCTIONS
// ════════════════════════════════════════════════════════════

/**
 * Fetches sent emails from the last N months for voice training.
 * params: { months_back (int), max_results (int) }
 */
function getSentEmails(params) {
  var monthsBack = params.months_back || 6;
  var maxResults = params.max_results || 200;

  var cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - monthsBack);
  var afterDate = Utilities.formatDate(cutoff, "UTC", "yyyy/MM/dd");

  var query = "in:sent after:" + afterDate;
  var threads = GmailApp.search(query, 0, maxResults);

  var emails = [];
  for (var i = 0; i < threads.length; i++) {
    var messages = threads[i].getMessages();
    // Only grab the first (most recent) message per thread
    var msg = messages[messages.length - 1];
    var body = msg.getPlainBody();

    if (!body || body.length < 80) continue;

    // Skip automated/calendar emails
    var lowerBody = body.toLowerCase();
    var lowerSubject = msg.getSubject().toLowerCase();
    var combined = lowerBody + lowerSubject;
    var skipKeywords = ["unsubscribe", "calendar invite", "zoom.us/j/", "auto-reply",
                        "out of office", "notification", "noreply", "no-reply", "donotreply"];
    var skip = false;
    for (var k = 0; k < skipKeywords.length; k++) {
      if (combined.indexOf(skipKeywords[k]) !== -1) { skip = true; break; }
    }
    if (skip) continue;

    emails.push({
      subject: msg.getSubject(),
      to: msg.getTo(),
      date: msg.getDate().toString(),
      body: body.substring(0, 3000) // Cap per email to avoid massive payloads
    });
  }

  return { success: true, emails: emails, count: emails.length };
}


/**
 * Creates a Gmail draft.
 * params: { to (str), subject (str), body (str) }
 */
function createDraft(params) {
  var to = params.to || "";
  var subject = params.subject || "(no subject)";
  var body = params.body || "";

  var draft = GmailApp.createDraft(to, subject, body);
  var draftId = draft.getId();

  return {
    success: true,
    draft_id: draftId,
    to: to,
    subject: subject,
    link: "https://mail.google.com/mail/u/0/#drafts"
  };
}


/**
 * Searches the inbox.
 * params: { query (str), max_results (int) }
 */
function searchInbox(params) {
  var query = params.query || "";
  var maxResults = params.max_results || 10;

  var threads = GmailApp.search(query, 0, maxResults);
  var results = [];

  for (var i = 0; i < threads.length; i++) {
    var msg = threads[i].getMessages()[0];
    results.push({
      subject: msg.getSubject(),
      from: msg.getFrom(),
      date: msg.getDate().toString(),
      snippet: msg.getPlainBody().substring(0, 300)
    });
  }

  return { success: true, results: results, count: results.length };
}


// ════════════════════════════════════════════════════════════
// CALENDAR FUNCTIONS
// ════════════════════════════════════════════════════════════

/**
 * Gets calendar events for a date range.
 * params: { days_ahead (int) } — defaults to today + 7 days
 */
function getCalendarEvents(params) {
  var daysAhead = params.days_ahead || 7;
  var now = new Date();
  var end = new Date();
  end.setDate(end.getDate() + daysAhead);

  var cal = CalendarApp.getDefaultCalendar();
  var events = cal.getEvents(now, end);

  var results = [];
  for (var i = 0; i < events.length; i++) {
    var ev = events[i];
    results.push({
      title: ev.getTitle(),
      start: ev.getStartTime().toString(),
      end: ev.getEndTime().toString(),
      location: ev.getLocation(),
      description: ev.getDescription().substring(0, 500),
      guests: ev.getGuestList().map(function(g) { return g.getEmail(); })
    });
  }

  return { success: true, events: results, count: results.length };
}


/**
 * Creates a calendar event.
 * params: { title, start_iso, end_iso, description, guests (array), location }
 */
function createCalendarEvent(params) {
  var cal = CalendarApp.getDefaultCalendar();
  var start = new Date(params.start_iso);
  var end = new Date(params.end_iso);

  var event = cal.createEvent(
    params.title || "Meeting",
    start,
    end,
    {
      description: params.description || "",
      location: params.location || "",
      guests: (params.guests || []).join(","),
      sendInvites: false  // Never auto-send invites
    }
  );

  return {
    success: true,
    event_id: event.getId(),
    title: event.getTitle(),
    start: event.getStartTime().toString(),
    link: "https://calendar.google.com/calendar/r"
  };
}


/**
 * Logs a sales call as a calendar event with structured notes.
 * params: { contact_name, title, district, date_iso, duration_minutes, notes, outcome, next_steps }
 */
function logCall(params) {
  var cal = CalendarApp.getDefaultCalendar();

  var start = new Date(params.date_iso || new Date());
  var durationMs = (params.duration_minutes || 30) * 60 * 1000;
  var end = new Date(start.getTime() + durationMs);

  var eventTitle = "📞 Call — " + (params.contact_name || "Contact") + " @ " + (params.district || "");

  var description = [
    "Contact: " + (params.contact_name || ""),
    "Title: " + (params.title || ""),
    "District: " + (params.district || ""),
    "",
    "Notes:",
    params.notes || "",
    "",
    "Outcome: " + (params.outcome || ""),
    "Next Steps: " + (params.next_steps || ""),
    "",
    "[Logged by Scout]"
  ].join("\n");

  var event = cal.createEvent(eventTitle, start, end, { description: description });

  return {
    success: true,
    event_id: event.getId(),
    title: eventTitle,
    link: "https://calendar.google.com/calendar/r"
  };
}


// ════════════════════════════════════════════════════════════
// SLIDES FUNCTIONS
// ════════════════════════════════════════════════════════════

/**
 * Creates a blank presentation.
 * params: { title }
 */
function createPresentation(params) {
  var pres = SlidesApp.create(params.title || "New Presentation");
  var url = pres.getUrl();
  var id = pres.getId();

  return { success: true, presentation_id: id, url: url, title: pres.getName() };
}


/**
 * Creates a district discovery / pitch deck.
 * params: {
 *   district_name, state, contact_name, contact_title,
 *   student_count, key_pain_points (array), products_to_highlight (array),
 *   case_study (str)
 * }
 */
function createDistrictDeck(params) {
  var district = params.district_name || "School District";
  var state = params.state || "";
  var contact = params.contact_name || "";
  var title = params.contact_title || "";
  var products = params.products_to_highlight || ["CodeCombat Classroom", "AI HackStack"];
  var painPoints = params.key_pain_points || [];
  var caseStudy = params.case_study || "";

  var deckTitle = "CodeCombat — " + district;
  var pres = SlidesApp.create(deckTitle);
  var slides = pres.getSlides();

  // ── Slide 1: Title ────────────────────────────────────────
  var slide1 = slides[0];
  slide1.getShapes()[0].getText().setText("CodeCombat K-12 CS + AI Suite");
  if (slide1.getShapes().length > 1) {
    slide1.getShapes()[1].getText().setText(district + (state ? ", " + state : "") + "\n" + (contact ? "For: " + contact + (title ? " — " + title : "") : ""));
  }

  // ── Slide 2: The Challenge ────────────────────────────────
  var slide2 = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
  slide2.getShapes()[0].getText().setText("The Challenge");
  var challengeBody = painPoints.length > 0
    ? painPoints.map(function(p) { return "• " + p; }).join("\n")
    : "• Engaging students in CS beyond worksheets\n• Teachers without deep CS backgrounds\n• Standards alignment and reporting\n• Limited budget, high expectations";
  slide2.getShapes()[1].getText().setText(challengeBody);

  // ── Slide 3: Our Solution ─────────────────────────────────
  var slide3 = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
  slide3.getShapes()[0].getText().setText("The CodeCombat Solution");
  slide3.getShapes()[1].getText().setText(
    "Game-based, narrative-driven CS learning that students actually want to do.\n\n" +
    "• Standards-aligned (CSTA, ISTE, CA CS Standards, NGSS)\n" +
    "• Turn-key teacher resources — no CS background needed\n" +
    "• Real code: Python, JavaScript, Lua\n" +
    "• AI literacy built in"
  );

  // ── Slide 4: Products ─────────────────────────────────────
  var slide4 = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
  slide4.getShapes()[0].getText().setText("Recommended for " + district);
  var productDescriptions = {
    "CodeCombat Classroom": "Game-based CS in Python/JS/Lua — Grades 6–12",
    "Ozaria": "Narrative RPG CS for middle school",
    "CodeCombat Junior": "Block-based coding — Grades K–5",
    "AI HackStack": "Hands-on AI literacy curriculum",
    "AI Junior": "AI curriculum for K–8",
    "AI League": "Esports coding tournaments",
    "AP CSP Course": "Full AP Computer Science Principles course"
  };
  var productBody = products.map(function(p) {
    return "• " + p + (productDescriptions[p] ? ": " + productDescriptions[p] : "");
  }).join("\n");
  slide4.getShapes()[1].getText().setText(productBody);

  // ── Slide 5: Case Study (if provided) ────────────────────
  if (caseStudy) {
    var slide5 = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
    slide5.getShapes()[0].getText().setText("Success Story");
    slide5.getShapes()[1].getText().setText(caseStudy);
  }

  // ── Slide 6: Next Steps ───────────────────────────────────
  var slideNext = pres.appendSlide(SlidesApp.PredefinedLayout.TITLE_AND_BODY);
  slideNext.getShapes()[0].getText().setText("Next Steps");
  slideNext.getShapes()[1].getText().setText(
    "• 30-minute demo — see the platform live\n" +
    "• Free pilot for your teachers\n" +
    "• Custom quote for " + district + "\n\n" +
    "Steven Adkin\nsteven@codecombat.com\ncodecombat.com"
  );

  pres.saveAndClose();

  return {
    success: true,
    presentation_id: pres.getId(),
    url: "https://docs.google.com/presentation/d/" + pres.getId() + "/edit",
    title: deckTitle,
    slide_count: 5 + (caseStudy ? 1 : 0)
  };
}


// ════════════════════════════════════════════════════════════
// HELPER
// ════════════════════════════════════════════════════════════

function jsonResponse(data, statusCode) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

// ════════════════════════════════════════════════════════════
// GOOGLE DOCS (Phase 5)
// ════════════════════════════════════════════════════════════

/**
 * Creates a new Google Doc in a specified Drive folder.
 * Phase 5: Used for pre-call briefs saved to "Scout Pre-Call Briefs" folder.
 *
 * params: { title (str), content (str), folder_id (str, optional) }
 * Returns: { success, doc_id, url, title }
 */
function createGoogleDoc(params) {
  var title   = params.title   || "Scout Doc";
  var content = params.content || "";
  var folderId = params.folder_id || "";

  // Create the document
  var doc = DocumentApp.create(title);
  var docId = doc.getId();

  // Write content to the body
  var body = doc.getBody();
  body.setText(content);
  doc.saveAndClose();

  // Move to specified folder if folder_id is provided
  if (folderId) {
    try {
      var file   = DriveApp.getFileById(docId);
      var folder = DriveApp.getFolderById(folderId);
      folder.addFile(file);
      // Remove from root (My Drive) to keep things tidy
      DriveApp.getRootFolder().removeFile(file);
    } catch (e) {
      // Non-fatal: Doc was created, just couldn't move it
      Logger.log("createGoogleDoc: could not move to folder " + folderId + " — " + e.toString());
    }
  }

  var url = "https://docs.google.com/document/d/" + docId + "/edit";
  return { success: true, doc_id: docId, url: url, title: title };
}
