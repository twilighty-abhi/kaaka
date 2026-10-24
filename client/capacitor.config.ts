import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.kaaka.sensors',
  appName: 'KaakaSensors',
  webDir: 'build',
  // Serve the app over http so the WebView may open ws:// to the Mac server
  // (an https page blocks insecure WebSockets as mixed content).
  server: {
    androidScheme: 'http',
    cleartext: true,
  },
};

export default config;
