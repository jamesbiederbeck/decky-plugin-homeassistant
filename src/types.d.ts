declare module "*.svg" {
  const content: string;
  export default content;
}

declare module "*.png" {
  const content: string;
  export default content;
}

declare module "*.jpg" {
  const content: string;
  export default content;
}

// Steam Client global types
declare global {
  interface Window {
    SteamClient: any;
  }
  
  const SteamClient: {
    GameSessions: {
      RegisterForAppLifetimeNotifications(
        callback: (notification: { unAppID: number; nInstanceID: number; bRunning: boolean }) => void
      ): { unregister: () => void };
    };
    Downloads: {
      RegisterForDownloadItems(
        callback: (isDownloading: boolean, downloadItems: any[]) => void
      ): { unregister: () => void };
      RegisterForDownloadOverview(
        callback: (overview: any) => void
      ): { unregister: () => void };
    };
    User: {
      RegisterForPrepareForSystemSuspendProgress(
        callback: (progress: any) => void
      ): { unregister: () => void };
      RegisterForResumeSuspendedGamesProgress(
        callback: (progress: any) => void
      ): { unregister: () => void };
      RegisterForShutdownStart(
        callback: (param0: any) => void
      ): { unregister: () => void };
    };
  };
}

export {};
