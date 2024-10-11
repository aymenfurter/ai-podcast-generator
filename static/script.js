let podcastScript = '';
let combinedTranscript = '';
let currentTurnNumber = 0;
let preloadedTurn = null;
let isPreloading = false;
let isPlaying = false;
let isProcessingPreloadedTurn = false;
let pendingAudienceQuestion = null;

const MAX_RETRIES = 3;
const RETRY_DELAY = 2000;

let audioContext, analyser, dataArray;
const FFT_SIZE = 32;
let animationFrameId = null;

function initAudio() {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = FFT_SIZE;
    dataArray = new Uint8Array(analyser.frequencyBinCount);
}

async function generatePodcastScript() {
    const topic = document.getElementById('topic').value.trim();
    if (!topic) {
        showNotification('Please enter content for the podcast.');
        return;
    }

    updateStatusMessage('Generating podcast...', true);
    clearRetryMessage();

    try {
        const response = await fetch('/generate_podcast_script', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ topic }),
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        podcastScript = data.podcast_script;

        document.getElementById('audienceQuestionInput').classList.remove('hidden');
        document.getElementById('topicInput').classList.add('hidden');
        
        startPodcast();
    } catch (error) {
        console.error('Error generating podcast script:', error);
        showNotification('An error occurred while generating the podcast. Please try again.');
    } finally {
        clearStatusMessage();
    }
}

async function startPodcast() {
    if (isPlaying) {
        return;
    }

    isPlaying = true;
    currentTurnNumber = 0;
    combinedTranscript = '';
    clearRetryMessage();

    const firstTurn = await fetchTurnWithRetry(currentTurnNumber);
    if (!firstTurn) {
        showNotification('No turns available to play.');
        isPlaying = false;
        return;
    }

    combinedTranscript += formatTranscript(firstTurn);

    preloadedTurn = await fetchTurnWithRetry(currentTurnNumber + 1);

    await playTurn(firstTurn);
}

async function fetchTurnWithRetry(turnNumber, attempt = 1) {
    if (turnNumber >= 7) {
        return null;
    }

    updateStatusMessage(`Fetching turn ${turnNumber} (Attempt ${attempt}/${MAX_RETRIES})...`, true);
    clearRetryMessage();

    try {
        let body = {
            podcast_script: podcastScript,
            combined_transcript: combinedTranscript,
            turn: turnNumber,
        };

        if (pendingAudienceQuestion) {
            body.audience_question = pendingAudienceQuestion;
            body.combined_transcript += `\n\nAudience: ${pendingAudienceQuestion}\nANSWER THE AUDIENCE QUESTION FIRST THEN MOVE ON`;
            pendingAudienceQuestion = null;
        } else {
            body.audience_question = "";
        }

        const response = await fetch('/next_turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch turn ${turnNumber}`);
        }

        const data = await response.json();

        if (!data.transcript || !data.audio_base64) {
            throw new Error(`Incomplete data for turn ${turnNumber}`);
        }

        let transcript = data.transcript.trim();

        if (!/[.!?]$/.test(transcript)) {
            const lastPeriod = transcript.lastIndexOf('.');
            const lastQuestion = transcript.lastIndexOf('?');
            const lastExclamation = transcript.lastIndexOf('!');
            const lastPunc = Math.max(lastPeriod, lastQuestion, lastExclamation);

            if (lastPunc !== -1) {
                transcript = transcript.substring(0, lastPunc + 1).trim();
            } else {
                transcript = '';
            }
        }

        return {
            turnNumber: turnNumber,
            transcript: transcript.startsWith(`${data.speaker}:`) ? transcript : `${data.speaker}: ${transcript}`,
            audio_base64: data.audio_base64,
        };
    } catch (error) {
        console.error(`Error fetching turn ${turnNumber}:`, error);
        if (attempt < MAX_RETRIES) {
            showRetryMessage(`Failed to load turn ${turnNumber}. Retrying in ${RETRY_DELAY / 1000} seconds...`);
            await delay(RETRY_DELAY);
            return await fetchTurnWithRetry(turnNumber, attempt + 1);
        } else {
            showRetryMessage(`Failed to load turn ${turnNumber} after ${MAX_RETRIES} attempts.`);
            return null;
        }
    } finally {
        clearStatusMessage();
    }
}

async function playTurn(turnData) {
    if (!turnData || !turnData.audio_base64) {
        console.error('Invalid turn data:', turnData);
        return;
    }

    updateAvatars();

    try {
        if (!audioContext) initAudio();

        const binaryString = atob(turnData.audio_base64);
        const len = binaryString.length;
        const pcmData = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            pcmData[i] = binaryString.charCodeAt(i);
        }

        const sampleRate = 24000;
        const numChannels = 1;
        const wavBuffer = pcm16ToWav(pcmData, sampleRate, numChannels);

        const audioBuffer = await audioContext.decodeAudioData(wavBuffer);

        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(analyser);
        analyser.connect(audioContext.destination);

        source.onended = async () => {
            isPlaying = false;
            currentTurnNumber++;

            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }

            stopVisualizer(document.querySelector('.avatar.active'));

            if (currentTurnNumber >= 7) {
                showNotification('Podcast has ended.');
                return;
            }

            if (preloadedTurn && !isProcessingPreloadedTurn) {
                isProcessingPreloadedTurn = true;
                combinedTranscript += `\n# Turn Number ${preloadedTurn.turnNumber}\n${preloadedTurn.transcript}`;

                await playTurn(preloadedTurn);

                preloadedTurn = null;
                isProcessingPreloadedTurn = false;

                if (currentTurnNumber < 6) {
                    preloadedTurn = await fetchTurnWithRetry(currentTurnNumber + 1);
                    if (!preloadedTurn) {
                        showNotification('Podcast has ended.');
                    }
                }
            } else {
                showNotification('Podcast has ended.');
            }
        };

        isPlaying = true;
        source.start(0);
        animateVisualizer();
    } catch (error) {
        console.error('Error playing audio:', error);
        showNotification('An error occurred during audio playback.');
        isPlaying = false
    }
}

function pcm16ToWav(pcmData, sampleRate = 24000, numChannels = 1) {
    const byteRate = sampleRate * numChannels * 2;
    const buffer = new ArrayBuffer(44 + pcmData.length);
    const view = new DataView(buffer);

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + pcmData.length, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, numChannels * 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, pcmData.length, true);

    const uint8Array = new Uint8Array(buffer, 44);
    uint8Array.set(pcmData);

    return buffer;
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

function formatTranscript(turnData) {
    return `${turnData.transcript}`;
}

function addAudienceQuestion() {
    const question = document.getElementById('question').value.trim();
    if (!question) {
        showNotification('Please enter a question.');
        return;
    }

    pendingAudienceQuestion = question;
    document.getElementById('question').value = '';
    showNotification('Question submitted. It will be answered in the next turn.');
}

function animateVisualizer() {
    const activeAvatar = document.querySelector('.avatar.active');
    if (!activeAvatar || !isPlaying) return;

    const bars = activeAvatar.querySelectorAll('.bar');
    const pulse = activeAvatar.querySelector('.pulse');

    analyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < bars.length; i++) {
        const value = dataArray[i];
        const percent = value / 255 * 100;
        bars[i].style.height = `${percent}%`;
        sum += value;
    }

    const average = sum / dataArray.length;
    const pulseScale = 1 + (average / 255) * 0.3; // Scale between 1 and 1.3
    pulse.style.transform = `scale(${pulseScale})`;

    animationFrameId = requestAnimationFrame(animateVisualizer);
}

function stopVisualizer(avatar) {
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }

    const bars = avatar.querySelectorAll('.bar');
    const pulse = avatar.querySelector('.pulse');
    bars.forEach(bar => {
        bar.style.height = '0%';
    });
    pulse.style.transform = 'scale(1)';
}

function updateAvatars() {
    const avatar1 = document.getElementById('avatar1');
    const avatar2 = document.getElementById('avatar2');
    avatar1.classList.toggle('active', currentTurnNumber % 2 === 0);
    avatar2.classList.toggle('active', currentTurnNumber % 2 !== 0);
    
    stopVisualizer(avatar1);
    stopVisualizer(avatar2);
}

function updateStatusMessage(message, isBlinking = false) {
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.textContent = message;
    statusMessage.classList.remove('hidden');
    if (isBlinking) {
        statusMessage.classList.add('blink');
    } else {
        statusMessage.classList.remove('blink');
    }
}

function clearStatusMessage() {
    const statusMessage = document.getElementById('statusMessage');
    statusMessage.textContent = '';
    statusMessage.classList.add('hidden');
    statusMessage.classList.remove('blink');
}

function showRetryMessage(message) {
    const retryDiv = document.getElementById('retryMessage');
    retryDiv.textContent = message;
    retryDiv.classList.remove('hidden');
}

function clearRetryMessage() {
    const retryDiv = document.getElementById('retryMessage');
    retryDiv.textContent = '';
    retryDiv.classList.add('hidden');
}

function showNotification(message, duration = 3000) {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.classList.add('show');
    setTimeout(() => {
        notification.classList.remove('show');
    }, duration);
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}