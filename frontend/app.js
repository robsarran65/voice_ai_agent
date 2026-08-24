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

// Confirmed via testing that no delay length fixes word-dropping on a
// Bluetooth mic (tried up to 2.5s) — it's an OS/Bluetooth-stack
// negotiation issue, not a capture-start timing issue. This is now
// just a reasonable floor for wired/built-in mics, where it does help.
const MIC_READY_DELAY_MS = 350;

// -------------------------------
// Audio priming (shared by mic input and TTS output)
// -------------------------------
let audioCtx = null;
function getAudioCtx() {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    if (!audioCtx) audioCtx = new Ctx();
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
}

// NOTE: we tried grabbing the mic via getUserMedia ahead of time (both
// grab-and-release per click, and grab-once-and-hold for the session)
// to work around Bluetooth headset profile-switch latency. Neither
// fixed the dropped opening words, and holding the stream open made
// output quality worse the whole session (forces the headset into its
// low-quality HFP profile permanently instead of just while actively
// listening). Removed — SpeechRecognition manages its own mic capture,
// and a competing getUserMedia stream was doing more harm than good.

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
        transcriptBox.innerText = "Getting ready...";
        setTimeout(() => {
            beep();
            transcriptBox.innerText = "Listening... speak now.";
        }, MIC_READY_DELAY_MS);
    };

    recognition.onresult = async (event) => {
        const text = event.results[event.results.length - 1][0].transcript;
        transcriptBox.innerText = text;

        // Send text to FastAPI backend
        const agentReply = await sendToBackend(text);

        // Display agent response
        agentBox.innerText = agentReply;

        // Speak agent response
        speak(agentReply);
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        transcriptBox.innerText = `Speech recognition error: ${event.error}`;
    };

    // continuous=false means recognition stops itself after one
    // utterance (or on error) — reset the buttons here so this covers
    // every stop path, not just the manual Stop click.
    recognition.onend = () => {
        listening = false;
        startBtn.disabled = false;
        stopBtn.disabled = true;
    };
} else {
    alert("Chrome Speech Recognition API not supported in this browser.");
}

// -------------------------------
// Start Listening
// -------------------------------
startBtn.onclick = () => {
    if (!listening) {
        listening = true;
        recognition.start();
        startBtn.disabled = true;
        stopBtn.disabled = false;
    }
};

// -------------------------------
// Stop Listening
// -------------------------------
stopBtn.onclick = () => {
    if (listening) {
        listening = false;
        recognition.stop();
        startBtn.disabled = false;
        stopBtn.disabled = true;
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

async function sendToBackend(text) {
    try {
        const response = await fetch(BACKEND_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ text })
        });

        if (!response.ok) {
            const body = await response.text();
            console.error("Backend returned an error:", response.status, body);
            return `Backend error ${response.status}: ${body}`;
        }

        const data = await response.json();
        return data.agent_message || "No response from agent.";
    } catch (err) {
        console.error("Backend error:", err);
        return `Error contacting backend (${BACKEND_URL}): ${err.message}`;
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
    warmAudioDevice();
    const utterance = new SpeechSynthesisUtterance(text);
    if (ttsVoice) utterance.voice = ttsVoice;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    speechSynthesis.speak(utterance);
}
