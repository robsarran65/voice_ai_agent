// ============================================================
// Voice AI Frontend (Chrome STT + Chrome TTS + FastAPI Client)
// ============================================================

// -------------------------------
// DOM Elements
// -------------------------------
const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const transcriptBox = document.getElementById("transcript");
const agentBox = document.getElementById("agent-response");
const replyPanel = document.getElementById("reply-panel");
const replyMeta = document.getElementById("reply-meta");
const orb = document.getElementById("orb");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("status-text");
const consoleLead = document.getElementById("console-lead");
const consoleHint = document.getElementById("console-hint");
const notice = document.getElementById("notice");
const noticeTitle = document.getElementById("notice-title");
const noticeBody = document.getElementById("notice-body");
const textAskForm = document.getElementById("text-ask-form");
const textAskInput = document.getElementById("text-ask-input");
const textAskBtn = document.getElementById("text-ask-btn");
const replayBtn = document.getElementById("replay-btn");

// Confirmed via testing that no delay length fixes word-dropping on a
// Bluetooth mic (tried up to 2.5s) — it's an OS/Bluetooth-stack
// negotiation issue, not a capture-start timing issue. This is now
// just a reasonable floor for wired/built-in mics, where it does help.
const MIC_READY_DELAY_MS = 350;

// -------------------------------
// Pipeline state
// -------------------------------
// The orb and the status line report the stage the request is actually
// in. Keeping the labels honest makes the demo debuggable in front of a
// client — if it stalls, the label says which stage it stalled at.
const STAGES = {
    idle: "Ready",
    starting: "Getting ready",
    listening: "Listening — speak now",
    thinking: "Thinking",
    speaking: "Speaking",
    unheard: "Didn't catch that — try again",
    error: "Something went wrong",
    blocked: "Voice input unavailable",
};

function setStage(stage) {
    orb.dataset.state = stage;
    statusEl.dataset.state = stage;
    statusText.textContent = STAGES[stage] || STAGES.idle;
}

// Writing through one helper keeps the empty-state placeholders in the
// CSS working — an element only shows its placeholder while it's empty.
function setText(el, text) {
    el.textContent = text || "";
    el.dataset.empty = text ? "false" : "true";
}

function showNotice(title, body) {
    noticeTitle.textContent = title;
    noticeBody.textContent = body;
    notice.hidden = false;
}

// -------------------------------
// Audio priming (shared by mic input and TTS output)
// -------------------------------
let audioCtx = null;
let speechUnlocked = false;
let activeUtterance = null;
function getAudioCtx() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtx) audioCtx = new Ctx();
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
}

function unlockSpeech() {
    getAudioCtx();
    if (!("speechSynthesis" in window) || speechUnlocked) return;
    const primer = new SpeechSynthesisUtterance(" ");
    primer.volume = 0;
    window.speechSynthesis.speak(primer);
    speechUnlocked = true;
}

// NOTE: we tried grabbing the mic via getUserMedia ahead of time (both
// grab-and-release per click, and grab-once-and-hold for the session)
// to work around Bluetooth headset profile-switch latency. Neither
// fixed the dropped opening words, and holding the stream open made
// output quality worse the whole session (forces the headset into its
// low-quality HFP profile permanently instead of just while actively
// listening). Removed — SpeechRecognition manages its own mic capture,
// and a competing getUserMedia stream was doing more harm than good.
//
// The orb animation is deliberately NOT driven by live mic amplitude for
// the same reason: an analyser node needs its own getUserMedia stream,
// which is exactly what made things worse. It animates per stage instead.

// An audible cue is a far more reliable "go" signal than on-screen text
// (which requires the user to be looking at the page) for the exact
// moment recognition actually starts capturing.
function beep() {
    try {
        const ctx = getAudioCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 880;
        gain.gain.value = 0.15;
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.1);
    } catch (e) {
        // Web Audio unsupported/blocked — the text cue is the fallback.
    }
}

// -------------------------------
// Chrome Speech Recognition Setup
// -------------------------------
let recognition;
let listening = false;

if ("webkitSpeechRecognition" in window) {
    recognition = new webkitSpeechRecognition();
    // Single utterance per Start click, not always-on. `continuous: true`
    // splits speech into a separate result on every natural pause (e.g.
    // "Hello Candy, [pause] how are you?") and fires onresult once per
    // segment — each firing overwrote the transcript box and sent its own
    // request, so only the last fragment ever appeared or got answered.
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    // onstart fires when the recognition SESSION begins, not necessarily
    // when audio capture is actually flowing — there can still be a real
    // gap after this event before Chrome is truly listening. A short
    // extra delay before the "go" cue accounts for that; tune
    // MIC_READY_DELAY_MS up/down based on how it tests in practice.
    recognition.onstart = () => {
        setStage("starting");
        setTimeout(() => {
            beep();
            setStage("listening");
        }, MIC_READY_DELAY_MS);
    };

    recognition.onresult = async (event) => {
        const text = event.results[event.results.length - 1][0].transcript;
        setText(transcriptBox, text);

        // Send text to FastAPI backend
        setStage("thinking");
        const reply = await sendToBackend(text);

        // Display agent response
        setText(agentBox, reply.message);
        replyPanel.dataset.ok = String(reply.ok);
        replyMeta.textContent = reply.meta;
        replayBtn.hidden = !reply.message;

        // Speak agent response
        speak(reply.message);
    };

    recognition.onerror = (event) => {
        const err = event.error;
        console.warn("Speech recognition ended with:", err);

        // The API reports ordinary outcomes through the same channel as real
        // faults. Saying "Something went wrong" when a user simply paused, or
        // pressed Stop, teaches them to distrust the indicator — so these two
        // are handled before anything is called an error.
        if (err === "aborted") {
            setStage("idle");
            return;
        }
        if (err === "no-speech") {
            setStage("unheard");
            return;
        }

        setStage("error");
        if (err === "not-allowed" || err === "service-not-allowed") {
            showNotice(
                "Microphone access is blocked",
                "Allow microphone access for this page in your browser's site settings, then press Talk to Candy again."
            );
        } else if (err === "audio-capture") {
            showNotice(
                "No microphone found",
                "Connect a microphone and check it's selected as the input device, then press Talk to Candy again."
            );
        } else if (err === "network") {
            showNotice(
                "Speech recognition needs a connection",
                "Chrome sends audio to Google's servers to transcribe it, and that request failed. Check your internet connection, then press Talk to Candy again."
            );
        } else {
            showNotice(
                "Speech recognition stopped",
                `The browser reported: ${err}. Press Talk to Candy to try again.`
            );
        }
    };

    // continuous=false means recognition stops itself after one
    // utterance (or on error) — reset the buttons here so this covers
    // every stop path, not just the manual Stop click.
    recognition.onend = () => {
        listening = false;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        // Don't stomp on a later stage: by the time recognition ends we may
        // already be thinking or speaking about what it captured.
        if (["starting", "listening"].includes(orb.dataset.state)) setStage("idle");
    };
} else {
    // iOS browsers may not expose speech recognition, but typed questions
    // keep the full assistant and spoken-answer experience available.
    startBtn.disabled = true;
    stopBtn.disabled = true;
    setStage("blocked");
    // Telling someone to press a button that is disabled reads as a bug.
    consoleLead.textContent = "Type a question for Candy.";
    consoleHint.textContent = "Voice input isn't available here, but Candy can still answer and speak aloud.";
    showNotice(
        "Voice input isn't available in this browser",
        "Type your question below and tap Ask. Candy's answer will appear and play aloud; tap Hear answer if iPhone blocks automatic playback."
    );
}

// -------------------------------
// Start Listening
// -------------------------------
startBtn.onclick = () => {
    if (!listening) {
        unlockSpeech();
        listening = true;
        notice.hidden = true;
        recognition.start();
        startBtn.disabled = true;
        stopBtn.disabled = false;
    }
};

async function askCandy(text) {
    unlockSpeech();
    setText(transcriptBox, text);
    setStage("thinking");
    textAskBtn.disabled = true;
    const reply = await sendToBackend(text);
    setText(agentBox, reply.message);
    replyPanel.dataset.ok = String(reply.ok);
    replyMeta.textContent = reply.meta;
    replayBtn.hidden = !reply.message;
    textAskBtn.disabled = false;
    speak(reply.message);
}

textAskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = textAskInput.value.trim();
    if (!text) return;
    await askCandy(text);
});

replayBtn.addEventListener("click", () => {
    unlockSpeech();
    speak(agentBox.textContent);
});

// -------------------------------
// Stop Listening
// -------------------------------
stopBtn.onclick = () => {
    if (listening) {
        listening = false;
        recognition.stop();
        startBtn.disabled = false;
        stopBtn.disabled = true;
        setStage("idle");
    }
};

// -------------------------------
// Send Text to FastAPI Backend
// -------------------------------
// When served from the same domain as the API (e.g. on Vercel, per
// vercel.json's routing), a relative path is correct. When served
// locally from a dev server on localhost, the API runs separately
// on port 8000.
const BACKEND_URL =
    ["localhost", "127.0.0.1"].includes(window.location.hostname)
        ? "http://127.0.0.1:8000/voice-chat/"
        : "/voice-chat/";

// Everything Candy might say out loud has to survive being spoken, so the
// failure branches return a plain sentence rather than a status code. The
// technical detail goes to `meta` and the console, where it belongs.
// One id per tab, so a calendar event Candy proposes on one turn can be
// confirmed on the next. Not persisted: a reload should start clean rather
// than inherit a half-finished confirmation.
const SESSION_ID = (crypto.randomUUID && crypto.randomUUID()) ||
    String(Date.now()) + Math.random().toString(16).slice(2);

async function sendToBackend(text) {
    try {
        const response = await fetch(BACKEND_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ text, session_id: SESSION_ID })
        });

        if (!response.ok) {
            const body = await response.text();
            console.error("Backend returned an error:", response.status, body);
            return {
                ok: false,
                message: "I couldn't reach my backend just then. Give it another try.",
                meta: `Backend responded ${response.status}`,
            };
        }

        const data = await response.json();
        return {
            // The API reports `ok: false` when the reply came from its
            // failure path rather than the model, so the panel can look
            // different even though both arrive as HTTP 200.
            ok: data.ok !== false,
            message: data.agent_message || "No response from agent.",
            meta: data.ok === false
                ? "Model unreachable — this came from Candy's fallback"
                : (data.model ? `Answered by ${data.model}` : ""),
        };
    } catch (err) {
        console.error("Backend error:", err);
        return {
            ok: false,
            message: "I can't reach my backend from here. Check that it's running, then try again.",
            meta: `No response from ${BACKEND_URL}`,
        };
    }
}

// -------------------------------
// Chrome Text-to-Speech (Candy's voice)
// -------------------------------
// Pin ONE consistent voice so Candy sounds the same every time, instead
// of whatever the browser/OS happens to default to. Same preference
// order validated in Jarvis 2 — first match wins, falls back gracefully
// if the exact voice isn't installed on this machine.
let ttsVoice = null;
function pickVoice() {
    const voices = speechSynthesis.getVoices() || [];
    const PREFS = [
        "Google UK English Female",
        "Microsoft Sonia", "Microsoft Libby",
        "Microsoft Hazel", "Microsoft Susan",
        "Microsoft Ryan", "Microsoft George",
        "Google UK English Male",
    ];
    let chosen = null;
    for (const name of PREFS) {
        chosen = voices.find((v) => v.name.indexOf(name) !== -1);
        if (chosen) break;
    }
    ttsVoice = chosen ||
        voices.find((v) => /en[-_]GB/i.test(v.lang)) ||
        voices.find((v) => /^en[-_]/i.test(v.lang)) ||
        voices[0] || null;
}
pickVoice();
speechSynthesis.onvoiceschanged = pickVoice; // voices load asynchronously in Chrome

// Chrome clips the first word or two of the first utterance while the
// audio output device cold-starts (e.g. "Good morning, sir" -> only
// "sir" is heard). An inaudible Web Audio blip wakes the device first.
function warmAudioDevice() {
    try {
        const ctx = getAudioCtx();
        if (!ctx) return;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        gain.gain.value = 0; // inaudible
        osc.connect(gain).connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.05);
    } catch (e) {
        // Web Audio unsupported/blocked — speech may clip its first word.
    }
}

function speak(text) {
    if (!("speechSynthesis" in window) || !text) {
        setStage("idle");
        return;
    }
    warmAudioDevice();
    const utterance = new SpeechSynthesisUtterance(text);
    if (ttsVoice) utterance.voice = ttsVoice;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    // Drive the orb from the utterance itself rather than guessing at a
    // duration, so the animation stops exactly when Candy stops talking.
    utterance.onstart = () => setStage("speaking");
    utterance.onend = () => {
        activeUtterance = null;
        setStage("idle");
    };
    utterance.onerror = () => {
        activeUtterance = null;
        setStage("idle");
    };
    activeUtterance = utterance; // iOS can drop an utterance that is garbage-collected.
    speechSynthesis.cancel();
    speechSynthesis.resume();
    speechSynthesis.speak(activeUtterance);
}
