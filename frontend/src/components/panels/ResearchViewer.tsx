import { useState, useEffect } from 'react';

interface DossierMeta {
  filename: string;
  size_bytes: number;
  modified: number;
  title: string;
}

interface Props {
  onClose: () => void;
  initialFilename?: string | null;
}

export default function ResearchViewer({ onClose, initialFilename }: Props) {
  const [dossiers, setDossiers] = useState<DossierMeta[]>([]);
  const [selectedFilename, setSelectedFilename] = useState<string | null>(initialFilename || null);
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    const fetchList = async () => {
      try {
        const res = await fetch('/api/research/dossiers');
        const data = await res.json();
        if (data && data.dossiers) {
          setDossiers(data.dossiers);
          setSelectedFilename(current => current ?? data.dossiers[0]?.filename ?? null);
        }
      } catch (err) {
        console.error('Failed to load dossiers:', err);
      }
    };
    fetchList();
  }, []);

  useEffect(() => {
    if (!selectedFilename) return;
    const fetchContent = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/research/dossier/${encodeURIComponent(selectedFilename)}`);
        const data = await res.json();
        if (data && data.content) {
          setContent(data.content);
        } else {
          setContent('# Error\n\nCould not load dossier content.');
        }
      } catch {
        setContent('# Network Error\n\nFailed to reach research archive.');
      } finally {
        setLoading(false);
      }
    };
    fetchContent();
  }, [selectedFilename]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xl p-6 md:p-12 animate-fade-in">
      <div className="relative w-full max-w-5xl h-[85vh] bg-[#0c0f17] border border-white/10 rounded-2xl flex flex-col overflow-hidden shadow-2xl persona-glow">
        
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full persona-bg animate-pulse" />
            <div>
              <h2 className="text-xs font-semibold tracking-[0.25em] text-white/90 uppercase">
                Deep Research Intelligence Archive
              </h2>
              <span className="text-[10px] tracking-wider text-white/40 font-mono">
                AUTONOMOUS MULTI-AGENT SYNTHESIZER
              </span>
            </div>
          </div>
          
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg border border-white/10 text-white/60 hover:text-white hover:bg-white/5 transition-all text-xs tracking-wider uppercase font-mono"
          >
            [Close ✕]
          </button>
        </div>

        {/* Content Area (Sidebar + Viewer) */}
        <div className="flex-1 flex overflow-hidden">
          {/* Dossier List Sidebar */}
          <div className="w-72 border-r border-white/10 overflow-y-auto bg-black/20 p-3 flex flex-col gap-2">
            <span className="text-[9px] tracking-[0.2em] text-white/30 uppercase font-mono px-2 py-1">
              Compiled Briefs ({dossiers.length})
            </span>
            {dossiers.map(d => (
              <button
                key={d.filename}
                onClick={() => setSelectedFilename(d.filename)}
                className={`w-full text-left p-2.5 rounded-xl border transition-all text-xs flex flex-col gap-1 ${
                  selectedFilename === d.filename
                    ? 'border-white/25 bg-white/[0.08] text-white'
                    : 'border-transparent text-white/60 hover:bg-white/[0.03] hover:text-white/80'
                }`}
              >
                <span className="font-medium truncate">{d.title}</span>
                <span className="text-[9px] text-white/30 font-mono">
                  {new Date(d.modified * 1000).toLocaleDateString()} • {(d.size_bytes / 1024).toFixed(1)} KB
                </span>
              </button>
            ))}
            {dossiers.length === 0 && (
              <div className="p-4 text-center text-white/30 text-xs font-mono">
                No research dossiers compiled yet. Ask Alfred: "Research [topic]"
              </div>
            )}
          </div>

          {/* Markdown Reader Body */}
          <div className="flex-1 overflow-y-auto p-8 font-sans text-white/80 text-sm leading-relaxed bg-[#0e121b]">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-white/40 font-mono text-xs">
                <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>Decrypting Research Dossier...</span>
              </div>
            ) : content ? (
              <div className="max-w-3xl mx-auto whitespace-pre-wrap font-mono text-xs leading-6 text-white/80 select-text">
                {content}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-white/30 font-mono text-xs">
                Select a dossier from the left archive.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
