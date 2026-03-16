# ============================================================
# TRADE CREDIT INSURANCE -- NOVA SONIC VOICE AGENT
# ============================================================
# Real-time voice conversation using Amazon Nova 2 Sonic.
# Customer speaks -> Nova Sonic transcribes and responds
# with voice using bidirectional streaming API.
#
# Architecture:
#   Microphone -> PyAudio -> Nova Sonic -> Speaker
#                               |
#                          Text transcript
#                               |
#                        TCI Strands Agent
#
# API: InvokeModelWithBidirectionalStream
# SDK: aws_sdk_bedrock_runtime (experimental)
# ============================================================

import asyncio
import base64
import boto3
import json
import uuid
import logging
import pyaudio

from aws_sdk_bedrock_runtime.client import (
    BedrockRuntimeClient,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from aws_sdk_bedrock_runtime.models import (
    InvokeModelWithBidirectionalStreamInputChunk,
    BidirectionalInputPayloadPart,
)
from aws_sdk_bedrock_runtime.config import (
    Config,
    HTTPAuthSchemeResolver,
    SigV4AuthScheme,
)
from smithy_core.shapes import ShapeID

from config import AWS_REGION

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# ============================================================
# SECTION 1 -- AUDIO CONFIGURATION
# ============================================================
# Nova Sonic requires specific audio formats:
#   Input  : 16kHz, 16-bit PCM, mono
#   Output : 24kHz, 16-bit PCM, mono, base64 encoded

INPUT_SAMPLE_RATE = 16000  # microphone input rate
OUTPUT_SAMPLE_RATE = 24000  # Nova Sonic output rate
CHANNELS = 1  # mono audio
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024  # audio chunk size in frames

# Nova Sonic model ID
NOVA_SONIC_MODEL_ID = "amazon.nova-2-sonic-v1:0"

# ============================================================
# SECTION 2 -- SYSTEM PROMPT FOR VOICE AGENT
# ============================================================

VOICE_SYSTEM_PROMPT = """
You are Alex, a senior Trade Credit Insurance underwriter at TCI Shield.

Your role is to conduct a voice-based insurance application interview.
Keep responses SHORT and conversational -- maximum 2 sentences per response.
Ask only ONE question at a time.
Speak naturally as if on a phone call.

Collect the following information in this exact order:

1. Business name and industry
2. Country where the business is based
3. Trade type -- export, domestic, or both
4. Annual turnover in GBP
5. Credit sales percentage
6. Years in business
7. Total number of buyers
8. For EACH buyer -- name, country, industry, and credit exposure in GBP
9. Standard payment terms in days
10. Largest single buyer as percentage of total exposure
11. Historical bad debt loss ratio as a decimal
12. Financial figures -- ask for all 11 in one go:
    annual revenue, current assets, current liabilities,
    total liabilities, tangible net worth, total assets,
    capital, bad debts, debtors, creditors, cost of sales

When all information is collected, summarise what you have gathered
and tell the customer their application will now be processed.
"""
# ============================================================
# SECTION 3 -- NOVA SONIC CLIENT
# ============================================================

class NovaSonicVoiceAgent:
    """
    Real-time voice agent using Amazon Nova 2 Sonic.
    Handles bidirectional audio streaming with Nova Sonic.
    """

    def __init__(self):
        self.model_id = NOVA_SONIC_MODEL_ID
        self.region = AWS_REGION
        self.client = None
        self.stream = None
        self.is_active = False
        self.prompt_name = str(uuid.uuid4())
        self.content_name = str(uuid.uuid4())
        self.audio_content_name = str(uuid.uuid4())
        self.audio_queue = asyncio.Queue()
        self.transcript = []  # stores conversation transcript
        self.collected_text = ""  # accumulates assistant text response
        self.alex_is_speaking = False

    # ----------------------------------------------------------
    # SECTION 3.1 -- CLIENT INITIALIZATION
    # ----------------------------------------------------------

    def _initialize_client(self):
        import boto3
        from smithy_aws_core.identity.static import StaticCredentialsResolver

        session = boto3.session.Session()
        creds = session.get_credentials().get_frozen_credentials()

        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=StaticCredentialsResolver(),
            aws_access_key_id=creds.access_key,
            aws_secret_access_key=creds.secret_key,
            aws_session_token=creds.token,
            auth_scheme_resolver=HTTPAuthSchemeResolver(),
            auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")}
        )
        self.client = BedrockRuntimeClient(config=config)
        logging.info("Nova Sonic client initialized")

    # ----------------------------------------------------------
    # SECTION 3.2 -- EVENT SENDER
    # ----------------------------------------------------------

    async def send_event(self, event_json: str):
        """
        Sends a JSON event to the Nova Sonic bidirectional stream.
        All communication with Nova Sonic is through JSON events.
        """
        event = InvokeModelWithBidirectionalStreamInputChunk(
            value=BidirectionalInputPayloadPart(
                bytes_=event_json.encode("utf-8")
            )
        )
        await self.stream.input_stream.send(event)

    # ----------------------------------------------------------
    # SECTION 3.3 -- SESSION START
    # ----------------------------------------------------------

    async def start_session(self):
        """
        Starts a Nova Sonic session with:
        1. Session configuration (inference params)
        2. Prompt start (voice settings)
        3. System prompt (Alex the underwriter)
        4. Content start (ready for audio)
        """
        if not self.client:
            self._initialize_client()

        # Open bidirectional stream
        self.stream = await self.client.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(
                model_id=self.model_id
            )
        )
        self.is_active = True
        logging.info("Nova Sonic bidirectional stream opened")

        # Event 1 -- Session start with inference config
        session_start = json.dumps({
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": 1024,
                        "topP": 0.9,
                        "temperature": 0.7
                    },
                    "turnDetectionConfiguration": {
                        "endpointingSensitivity": "HIGH"
                    }
                }
            }
        })
        await self.send_event(session_start)

        # Event 2 -- Prompt start with audio output config
        prompt_start = json.dumps({
            "event": {
                "promptStart": {
                    "promptName": self.prompt_name,
                    "textOutputConfiguration": {
                        "mediaType": "text/plain"
                    },
                    "audioOutputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": OUTPUT_SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": CHANNELS,
                        "voiceId": "matthew",  # masculine British voice
                        "encoding": "base64",
                        "audioType": "SPEECH"
                    }
                }
            }
        })
        await self.send_event(prompt_start)

        # Event 3 -- System prompt (Alex the underwriter)
        text_content_start = json.dumps({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": self.content_name,
                    "type": "TEXT",
                    "interactive": True,
                    "role": "SYSTEM",
                    "textInputConfiguration": {
                        "mediaType": "text/plain"
                    }
                }
            }
        })
        await self.send_event(text_content_start)

        # Send system prompt text
        system_prompt_event = json.dumps({
            "event": {
                "textInput": {
                    "promptName": self.prompt_name,
                    "contentName": self.content_name,
                    "content": VOICE_SYSTEM_PROMPT
                }
            }
        })
        await self.send_event(system_prompt_event)

        # End system prompt content
        text_content_end = json.dumps({
            "event": {
                "contentEnd": {
                    "promptName": self.prompt_name,
                    "contentName": self.content_name,
                }
            }
        })
        await self.send_event(text_content_end)

        # Event 4 -- Audio content start (ready to receive audio)
        audio_content_start = json.dumps({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
                    "type": "AUDIO",
                    "interactive": True,
                    "role": "USER",
                    "audioInputConfiguration": {
                        "mediaType": "audio/lpcm",
                        "sampleRateHertz": INPUT_SAMPLE_RATE,
                        "sampleSizeBits": 16,
                        "channelCount": CHANNELS,
                        "audioType": "SPEECH",
                        "encoding": "base64"
                    }
                }
            }
        })
        await self.send_event(audio_content_start)
        logging.info("Nova Sonic session started -- ready for audio")

    # ----------------------------------------------------------
    # SECTION 3.4 -- AUDIO INPUT
    # ----------------------------------------------------------

    async def send_audio_chunk(self, audio_data: bytes):
        """
        Sends a chunk of microphone audio to Nova Sonic.
        Audio must be base64 encoded before sending.
        """
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        audio_event = json.dumps({
            "event": {
                "audioInput": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
                    "content": audio_b64
                }
            }
        })
        await self.send_event(audio_event)

    async def end_audio_input(self):
        """Signals end of audio input to Nova Sonic."""
        content_end = json.dumps({
            "event": {
                "contentEnd": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
                }
            }
        })
        await self.send_event(content_end)

    # ----------------------------------------------------------
    # SECTION 3.5 -- RESPONSE PROCESSING
    # ----------------------------------------------------------

    async def process_responses(self):
        """
        Processes incoming responses from Nova Sonic.
        Handles three response types:
        - audioOutput  : Nova's spoken response (play to speaker)
        - textOutput   : Nova's text transcript (display/log)
        - contentEnd   : End of response turn
        """
        try:
            while self.is_active:
                output = await self.stream.await_output()
                result = await output[1].receive()

                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode("utf-8")
                    json_data = json.loads(response_data)

                    if "event" in json_data:
                        event = json_data["event"]

                        # Handle audio output -- queue for playback
                        if "audioOutput" in event:
                            audio_content = event["audioOutput"].get("content", "")
                            if audio_content:
                                self.alex_is_speaking = True
                                audio_bytes = base64.b64decode(audio_content)
                                await self.audio_queue.put(audio_bytes)

                        # Handle text output -- log transcript
                        elif "textOutput" in event:
                            text = event["textOutput"].get("content", "")
                            role = event["textOutput"].get("role", "")
                            if text and role == "ASSISTANT":
                                if text.strip().startswith("{"):
                                    continue
                                self.collected_text += text
                                print(f"\nAlex: {text}", end="", flush=True)
                            elif text and role == "USER":
                                print(f"\nYou : {text}", end="", flush=True)
                                self.transcript.append({
                                    "role": "user",
                                    "content": text
                                })

                        # Handle content end -- response turn complete
                        elif "contentEnd" in event:
                            self.alex_is_speaking = False
                            if self.collected_text:
                                self.transcript.append({
                                    "role": "assistant",
                                    "content": self.collected_text
                                })
                                self.collected_text = ""

        except Exception as e:
            if self.is_active:
                logging.error(f"Response processing error: {e}")

    # ----------------------------------------------------------
    # SECTION 3.6 -- AUDIO PLAYBACK
    # ----------------------------------------------------------

    async def play_audio(self):
        """
        Plays Nova Sonic's audio responses through the speaker.
        Reads from audio_queue which is filled by process_responses.
        """
        audio_handler = pyaudio.PyAudio()
        speaker_stream = audio_handler.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=OUTPUT_SAMPLE_RATE,
            output=True
        )
        try:
            while self.is_active:
                audio_data = await self.audio_queue.get()
                speaker_stream.write(audio_data)
        except Exception as e:
            logging.error(f"Audio playback error: {e}")
        finally:
            speaker_stream.stop_stream()
            speaker_stream.close()
            audio_handler.terminate()

    # ----------------------------------------------------------
    # SECTION 3.7 -- MICROPHONE CAPTURE
    # ----------------------------------------------------------

    async def capture_audio(self):
        """
        Captures audio from microphone and streams to Nova Sonic.
        Runs continuously until user presses Enter to stop.
        """
        audio_handler = pyaudio.PyAudio()
        mic_stream = audio_handler.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=INPUT_SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        logging.info("Microphone active -- speak now")
        print("\n" + "=" * 60)
        print("TCI Shield Voice Agent -- Alex is listening")
        print("Press Enter to end the conversation")
        print("=" * 60 + "\n")

        await asyncio.sleep(3)
        await self.start_audio_input()

        try:
            while self.is_active:
                audio_data = mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
                if not self.alex_is_speaking:
                    await self.send_audio_chunk(audio_data)
                await asyncio.sleep(0.01)
        except Exception as e:
            logging.error(f"Audio capture error: {e}")
        finally:
            mic_stream.stop_stream()
            mic_stream.close()
            audio_handler.terminate()
            await self.end_audio_input()
            logging.info("Microphone stopped")

    async def start_audio_input(self):
        """Signals to Nova Sonic that audio input is starting."""
        logging.info("Audio input starting")

    # ----------------------------------------------------------
    # SECTION 3.8 -- SESSION END
    # ----------------------------------------------------------

    async def end_session(self):
        """Gracefully ends the Nova Sonic session."""
        self.is_active = False

        # Send prompt end event
        prompt_end = json.dumps({
            "event": {
                "promptEnd": {
                    "promptName": self.prompt_name
                }
            }
        })
        try:
            await self.send_event(prompt_end)
        except Exception:
            pass

        # Send session end event
        session_end = json.dumps({
            "event": {
                "sessionEnd": {}
            }
        })
        try:
            await self.send_event(session_end)
            await self.stream.input_stream.close()
        except Exception:
            pass

        logging.info("Nova Sonic session ended")

        # Print transcript summary
        if self.transcript:
            print("\n" + "=" * 60)
            print("Conversation Transcript:")
            print("=" * 60)
            for entry in self.transcript:
                role = "Alex" if entry["role"] == "assistant" else "You"
                print(f"{role}: {entry['content']}")


# ============================================================
# SECTION 4 -- MAIN CONVERSATION LOOP
# ============================================================

async def run_voice_conversation():
    """
    Runs a complete voice conversation with Nova Sonic.
    Starts microphone capture, response processing, and
    audio playback as concurrent async tasks.
    """
    agent = NovaSonicVoiceAgent()

    # Start the session
    await agent.start_session()

    # Run three tasks concurrently:
    # 1. capture_audio    -- reads from mic, sends to Nova Sonic
    # 2. process_responses -- receives from Nova Sonic, queues audio + text
    # 3. play_audio       -- plays queued audio through speaker
    # 4. wait_for_enter   -- waits for user to press Enter to stop

    async def wait_for_enter():
        """Waits for Enter key press then ends session."""
        await asyncio.get_event_loop().run_in_executor(None, input)
        agent.is_active = False
        await agent.end_session()

    tasks = [
        asyncio.create_task(agent.capture_audio()),
        asyncio.create_task(agent.process_responses()),
        asyncio.create_task(agent.play_audio()),
        asyncio.create_task(wait_for_enter()),
    ]

    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info("Voice conversation complete")
    # Once voice conversation ends, pass transcript to underwriting agent
    if agent.transcript:
        print("\n" + "=" * 60)
        print("Processing your application through underwriting...")
        print("=" * 60 + "\n")

        transcript_text = "\n".join([
            f"{'Customer' if t['role'] == 'user' else 'Alex'}: {t['content']}"
            for t in agent.transcript
        ])

        summary_prompt = f"""
        The following is a completed voice conversation where a customer applied
        for trade credit insurance.

        {transcript_text}

        INSTRUCTIONS:
        1. Extract ALL information from the transcript
        2. Call collect_business_info with the business details
        3. Call set_buyer_count then collect_buyer_info with buyer details
        4. Call collect_financial_data with the financial figures
        5. Call run_underwriting immediately
        6. Call generate_policy_options immediately
        7. Automatically select option_2 and call issue_policy with option_2
        8. Do NOT wait for user input at any step
        9. Do NOT ask any questions -- just process and issue the policy
        """

        from tci_agent import run_underwriting_from_transcript
        run_underwriting_from_transcript(summary_prompt)

        from tci_agent import session
        if session.get("selected_policy"):
            print(f"\nPolicy issued: {session.get('selected_policy')}")
        else:
            print("\nPolicy not issued -- check underwriting logs above")

# ============================================================
# SECTION 5 -- ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("\nStarting TCI Shield Voice Agent...")
    print("Connecting to Amazon Nova Sonic...\n")
    asyncio.run(run_voice_conversation())
