import { SvgFilters } from './components/SvgFilters';
import { LandingScreen } from './components/LandingScreen';
import { ProcessingScreen } from './components/ProcessingScreen';
import { SpaceScene } from './components/SpaceScene';
import { SpaceHud } from './components/SpaceHud';
import { PhotoLightbox } from './components/PhotoLightbox';
import { CameraLayer } from './components/CameraLayer';
import { useViewStore } from './store/viewStore';

export default function App() {
  const view = useViewStore((s) => s.view);

  return (
    <>
      <SvgFilters />
      {view === 'landing' && <LandingScreen />}
      {view === 'processing' && <ProcessingScreen />}
      {view === 'space' && (
        <>
          <CameraLayer />
          <SpaceScene />
          <SpaceHud />
          <PhotoLightbox />
        </>
      )}
    </>
  );
}
