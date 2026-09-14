export interface Photo {
  id: string;
  name: string;
  blobUrl: string;             // ObjectURL of the original file (used by lightbox <img>)
  canvas: HTMLCanvasElement;   // Pre-decoded 2D canvas used as the WebGL texture source
  aspectRatio: number;          // width / height of the original image
}
