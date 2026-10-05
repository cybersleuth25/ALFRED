import { useState, useEffect } from 'react';

interface MeetingFile {
  filename: string;
  path: string;
  modified: string;
  size_kb: number;
  title: string;
}

interface MeetingState {
  active: boolean;
  title: string;
  elapsed_seconds: number;
  frame_count: number;
}

interface MeetingNotetakerProps {
  personaColor: string;
}

export default function MeetingNotetaker({ personaColor }: MeetingNotetakerProps) {
  const [meetingState, setMeetingState] = useState<MeetingState>({
    active: false,
    title: '',
    elapsed_seconds: 0,
    frame_count: 0,
  });
  const [titleInput, setTitleInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeNotes, setActiveNotes] = useState<string>('');
  const [history, setHistory] = useState<MeetingFile[]>([]);
  const [selectedMeeting, setSelectedMeeting] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Poll meeting status every 2 seconds
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch('/api/meeting/status');
        if (res.ok) {
          const data: MeetingState = await res.json();
          setMeetingState(data);
          if (data.active && data.title) {
            setTitleInput(current => current || data.title);
          }
        }
      } catch {
        return;
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch past meetings list
  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/meeting/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data.meetings || []);
      }
    } catch {
      return;
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  // Timer counter for active recording
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    if (meetingState.active) {
      timer = setInterval(() => {
        setMeetingState(prev => ({
          ...prev,
          elapsed_seconds: prev.elapsed_seconds + 1,
        }));
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [meetingState.active]);

  const handleStart = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/meeting/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: titleInput.trim() || 'General Meeting' }),
      });
      if (res.ok) {
        const d = await res.json();
        setMeetingState(d.status);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/meeting/stop', { method: 'POST' });
      if (res.ok) {
        const d = await res.json();
        setMeetingState(d.status);
        setActiveNotes(d.notes || 'No notes generated.');
        fetchHistory();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectHistory = async (file: MeetingFile) => {
    setSelectedMeeting(file.filename);
    try {
      const res = await fetch(`/api/meeting/note/${file.filename}`);
      if (res.ok) {
        const d = await res.json();
        setActiveNotes(d.content);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleCopy = () => {
    if (!activeNotes) return;
    navigator.clipboard.writeText(activeNotes);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  return (
    <div className="w-full h-full flex flex-col p-6 overflow-hidden bg-[#08090d] text-zinc-200 font-mono">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 border-b border-[#1c2230] shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold tracking-widest uppercase text-white flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                meetingState.active ? 'bg-rose-500 animate-ping' : 'bg-zinc-600'
              }`}
            />
            MEETING & LECTURE NOTETAKER STUDIO
          </span>
          <span className="text-[10px] text-zinc-500 bg-[#121620] px-2 py-0.5 rounded border border-[#222838]">
            {meetingState.active ? 'STATUS: CAPTURING AUDIO' : 'STATUS: IDLE'}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs">
          {meetingState.active && (
            <div className="flex items-center gap-2 text-rose-400 font-bold bg-rose-950/40 px-3 py-1 rounded border border-rose-800">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
              <span>REC {formatTime(meetingState.elapsed_seconds)}</span>
            </div>
          )}
          <span className="text-zinc-500">VOICE ENGINE: GEMINI 2.5 FLASH</span>
        </div>
      </div>

      {/* Main Studio Body: 2 Columns */}
      <div className="flex-1 min-h-0 flex gap-6 pt-5 overflow-hidden">
        {/* Left Column: Recording Controls & Past Meetings Archive (Width: 360px) */}
        <div className="w-[360px] shrink-0 flex flex-col gap-4 overflow-hidden">
          {/* Active Session Card */}
          <div className="panel p-4 border border-[#222838] bg-[#0c0e14] flex flex-col gap-3 shrink-0">
            <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">
              SESSION CONFIGURATION
            </span>

            <div>
              <label className="text-[10px] text-zinc-500 block mb-1">
                MEETING / LECTURE TITLE:
              </label>
              <input
                type="text"
                value={titleInput}
                disabled={meetingState.active}
                onChange={e => setTitleInput(e.target.value)}
                placeholder="e.g. Q4 Architectural Review"
                className="w-full bg-[#121620] border border-[#293244] rounded px-3 py-2 text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {/* Live Audio Spectrum Mock */}
            <div className="h-10 bg-[#121620] border border-[#1e2434] rounded flex items-center justify-center gap-1 px-3">
              {[25, 45, 60, 30, 80, 50, 95, 70, 40, 85, 30, 60, 45, 90, 35, 50, 75, 20].map((h, i) => (
                <div
                  key={i}
                  className="w-1 transition-all duration-150"
                  style={{
                    height: meetingState.active ? `${Math.max(15, (h * ((i % 3) + 1)) % 100)}%` : '15%',
                    backgroundColor: meetingState.active ? personaColor : '#222838',
                  }}
                />
              ))}
            </div>

            {/* Trigger Button */}
            {!meetingState.active ? (
              <button
                onClick={handleStart}
                disabled={loading}
                className="w-full py-2.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs tracking-wider transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                style={{ backgroundColor: personaColor }}
              >
                <span>🎙️ START RECORDING</span>
              </button>
            ) : (
              <button
                onClick={handleStop}
                disabled={loading}
                className="w-full py-2.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs tracking-wider transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <span>SYNTHESIZING MINUTES VIA GEMINI...</span>
                ) : (
                  <span>🛑 STOP & GENERATE MINUTES</span>
                )}
              </button>
            )}
          </div>

          {/* Past Meetings List */}
          <div className="panel p-4 border border-[#222838] bg-[#0c0e14] flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between pb-2 border-b border-[#1c2230] mb-2">
              <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">
                ARCHIVED NOTES ({history.length})
              </span>
              <button
                onClick={fetchHistory}
                className="text-[9px] text-cyan-400 hover:underline"
              >
                REFRESH
              </button>
            </div>

            <div className="flex-1 overflow-y-auto flex flex-col gap-1.5 pr-1">
              {history.length === 0 ? (
                <div className="text-center py-8 text-zinc-600 text-xs">
                  No past meeting notes recorded.
                </div>
              ) : (
                history.map(item => {
                  const isSelected = selectedMeeting === item.filename;
                  return (
                    <div
                      key={item.filename}
                      onClick={() => handleSelectHistory(item)}
                      className={`p-2.5 rounded border text-left cursor-pointer transition-colors ${
                        isSelected
                          ? 'border-cyan-500 bg-[#161f30]'
                          : 'border-[#1e2434] bg-[#121620] hover:bg-[#181d2a]'
                      }`}
                    >
                      <div className="text-xs font-semibold text-zinc-200 truncate">
                        {item.title}
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-zinc-500 mt-1">
                        <span>{item.modified}</span>
                        <span>{item.size_kb} KB</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Live & Rendered Markdown Minutes Display */}
        <div className="flex-1 flex flex-col panel border border-[#222838] bg-[#0c0e14] overflow-hidden">
          {/* Header Action Bar */}
          <div className="p-3 border-b border-[#1c2230] flex items-center justify-between bg-[#0e1118]">
            <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider flex items-center gap-2">
              <span>📋</span> EXECUTIVE SUMMARY & ACTION ITEMS
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopy}
                disabled={!activeNotes}
                className="px-3 py-1 rounded bg-[#181d2a] hover:bg-[#202738] border border-[#293244] text-[10px] text-zinc-300 transition-colors disabled:opacity-40"
              >
                {copied ? '✓ COPIED' : 'COPY MARKDOWN'}
              </button>
            </div>
          </div>

          {/* Content Pane */}
          <div className="flex-1 p-6 overflow-y-auto text-xs text-zinc-200 leading-relaxed font-sans">
            {loading ? (
              <div className="h-full flex flex-col items-center justify-center gap-3 text-zinc-500 font-mono">
                <span className="w-6 h-6 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin" />
                <span>MULTIMODAL AUDIO ANALYSIS IN PROGRESS...</span>
              </div>
            ) : activeNotes ? (
              <div className="prose prose-invert max-w-none space-y-4">
                <div className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-300">
                  {activeNotes}
                </div>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center gap-2 text-zinc-600 font-mono text-xs text-center">
                <span>NO ACTIVE MEETING SELECTED</span>
                <span className="text-[11px] text-zinc-700">
                  Start a new session on the left or select an archived note to view structured minutes.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
