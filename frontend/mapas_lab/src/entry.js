// Punto de entrada del bundle vendorizado para /mapas-lab/.
//
// Junta en un solo archivo deck.gl (core/layers/mapbox/extensions), luma.gl
// y WeatherLayers GL, EN VERSIONES QUE CASAN entre si (una sola instancia de
// luma). Se compila una vez con `npm run build` y el resultado queda en
// mundo/static/js/mapas_lab_deck.js, que el template carga con un <script>.
//
// No usamos CDN suelto porque deck.gl solo publica el global `deck` y
// WeatherLayers ademas necesita el global `luma`; cargarlos por separado
// mezclaria dos versiones de luma y rompe el contexto WebGL.

import { MapboxOverlay } from '@deck.gl/mapbox';
import { ClipExtension } from '@deck.gl/extensions';
import * as WeatherLayers from 'weatherlayers-gl';

// Se expone lo minimo que consume el template. Fase 1: RasterLayer para
// temperatura. ParticleLayer queda listo para el viento (requiere u/v del
// backend) en una fase posterior. Se expone ademas el namespace completo de
// WeatherLayers para acceder a enums (ImageType.SCALAR, ImageInterpolation.CUBIC).
window.MapasLabDeck = {
  MapboxOverlay,
  ClipExtension,
  RasterLayer: WeatherLayers.RasterLayer,
  ParticleLayer: WeatherLayers.ParticleLayer,
  WL: WeatherLayers,
};
