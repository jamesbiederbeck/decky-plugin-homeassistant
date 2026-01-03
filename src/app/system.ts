/**
 * System Event Module
 * Captures Steam runtime events and sends them to the backend for Home Assistant integration.
 * 
 * This module subscribes to:
 * - Game lifecycle events (start/stop)
 * - Download lifecycle events (start/progress/complete)
 * - System lifecycle events (suspend/resume/shutdown)
 */

import { callable } from "@decky/api";

// Backend API call for event ingestion
const ingestEvent = callable<[event: SystemEvent], void>("ingest_event");

// Event types
export type EventType = 
  | "game_started"
  | "game_stopped"
  | "download_started"
  | "download_progress"
  | "download_completed"
  | "download_stopped"
  | "system_suspending"
  | "system_resuming"
  | "system_shutting_down";

// Event payload structure
export interface SystemEvent {
  type: EventType;
  timestamp: number;
  app_id?: number;
  app_name?: string;
  progress?: number;
  rate?: number;
  downloading?: boolean;
}

// Steam runtime event interfaces
interface AppLifetimeNotification {
  unAppID: number;
  nInstanceID: number;
  bRunning: boolean;
}

interface DownloadItem {
  active: boolean;
  appid: number;
  completed: boolean;
  downloaded_bytes: number;
  total_bytes: number;
  paused: boolean;
}

interface DownloadOverview {
  update_appid: number;
  update_bytes_downloaded: number;
  update_bytes_to_download: number;
  update_network_bytes_per_second: number;
  update_state: string;
}

interface SuspendProgress {
  // Steam suspend progress data structure
  [key: string]: any;
}

// Frontend state to suppress duplicate events
interface SystemState {
  currentAppId: number | null;
  isGameRunning: boolean;
  isDownloading: boolean;
  downloadAppId: number | null;
}

class SystemEventManager {
  private state: SystemState = {
    currentAppId: null,
    isGameRunning: false,
    isDownloading: false,
    downloadAppId: null,
  };

  private unregisterCallbacks: Array<() => void> = [];
  private initialized = false;

  /**
   * Initialize the event manager and subscribe to Steam runtime events.
   * This should be called exactly once at plugin startup.
   */
  public initialize() {
    if (this.initialized) {
      console.warn("[SystemEvents] Already initialized, skipping");
      return;
    }

    console.log("[SystemEvents] Initializing event subscriptions");

    try {
      // Subscribe to game lifecycle events
      this.subscribeToGameEvents();

      // Subscribe to download events
      this.subscribeToDownloadEvents();

      // Subscribe to system lifecycle events
      this.subscribeToSystemEvents();

      this.initialized = true;
      console.log("[SystemEvents] Successfully initialized");
    } catch (error) {
      console.error("[SystemEvents] Failed to initialize:", error);
    }
  }

  /**
   * Clean up all event subscriptions.
   */
  public cleanup() {
    console.log("[SystemEvents] Cleaning up event subscriptions");
    this.unregisterCallbacks.forEach(unregister => {
      try {
        unregister();
      } catch (error) {
        console.error("[SystemEvents] Error during cleanup:", error);
      }
    });
    this.unregisterCallbacks = [];
    this.initialized = false;
  }

  /**
   * Subscribe to game lifecycle events.
   */
  private subscribeToGameEvents() {
    if (typeof SteamClient === "undefined" || !SteamClient.GameSessions) {
      console.warn("[SystemEvents] SteamClient.GameSessions not available");
      return;
    }

    try {
      const unregister = SteamClient.GameSessions.RegisterForAppLifetimeNotifications(
        (notification) => {
          this.handleGameLifetimeEvent(notification);
        }
      );
      this.unregisterCallbacks.push(unregister.unregister);
      console.log("[SystemEvents] Subscribed to game lifetime events");
    } catch (error) {
      console.error("[SystemEvents] Failed to subscribe to game events:", error);
    }
  }

  /**
   * Subscribe to download events.
   */
  private subscribeToDownloadEvents() {
    if (typeof SteamClient === "undefined" || !SteamClient.Downloads) {
      console.warn("[SystemEvents] SteamClient.Downloads not available");
      return;
    }

    try {
      // Subscribe to download items (queue state)
      const unregisterItems = SteamClient.Downloads.RegisterForDownloadItems(
        (isDownloading, downloadItems) => {
          this.handleDownloadItemsEvent(isDownloading, downloadItems);
        }
      );
      this.unregisterCallbacks.push(unregisterItems.unregister);

      // Subscribe to download overview (progress/rate)
      const unregisterOverview = SteamClient.Downloads.RegisterForDownloadOverview(
        (overview) => {
          this.handleDownloadOverviewEvent(overview);
        }
      );
      this.unregisterCallbacks.push(unregisterOverview.unregister);

      console.log("[SystemEvents] Subscribed to download events");
    } catch (error) {
      console.error("[SystemEvents] Failed to subscribe to download events:", error);
    }
  }

  /**
   * Subscribe to system lifecycle events.
   */
  private subscribeToSystemEvents() {
    if (typeof SteamClient === "undefined" || !SteamClient.User) {
      console.warn("[SystemEvents] SteamClient.User not available");
      return;
    }

    try {
      // Subscribe to suspend preparation
      const unregisterSuspend = SteamClient.User.RegisterForPrepareForSystemSuspendProgress(
        (progress) => {
          this.handleSystemSuspendEvent(progress);
        }
      );
      this.unregisterCallbacks.push(unregisterSuspend.unregister);

      // Subscribe to resume from suspend
      const unregisterResume = SteamClient.User.RegisterForResumeSuspendedGamesProgress(
        (progress) => {
          this.handleSystemResumeEvent(progress);
        }
      );
      this.unregisterCallbacks.push(unregisterResume.unregister);

      // Subscribe to shutdown start
      const unregisterShutdown = SteamClient.User.RegisterForShutdownStart(
        (param0) => {
          this.handleSystemShutdownEvent(param0);
        }
      );
      this.unregisterCallbacks.push(unregisterShutdown.unregister);

      console.log("[SystemEvents] Subscribed to system lifecycle events");
    } catch (error) {
      console.error("[SystemEvents] Failed to subscribe to system events:", error);
    }
  }

  /**
   * Handle game lifetime events (game started/stopped).
   */
  private handleGameLifetimeEvent(notification: AppLifetimeNotification) {
    const appId = notification.unAppID;
    const isRunning = notification.bRunning;

    console.debug("[SystemEvents] Game lifetime event:", { appId, isRunning });

    // Check if this is a duplicate event
    if (isRunning && this.state.isGameRunning && this.state.currentAppId === appId) {
      console.debug("[SystemEvents] Suppressing duplicate game_started event");
      return;
    }

    if (!isRunning && !this.state.isGameRunning) {
      console.debug("[SystemEvents] Suppressing duplicate game_stopped event");
      return;
    }

    // Update state
    this.state.isGameRunning = isRunning;
    this.state.currentAppId = isRunning ? appId : null;

    // Emit event
    const event: SystemEvent = {
      type: isRunning ? "game_started" : "game_stopped",
      timestamp: Date.now(),
      app_id: appId,
    };

    this.emitEvent(event);
  }

  /**
   * Handle download items events (download queue state).
   */
  private handleDownloadItemsEvent(isDownloading: boolean, downloadItems: DownloadItem[]) {
    console.debug("[SystemEvents] Download items event:", { isDownloading, count: downloadItems.length });

    // Check for state changes
    const wasDownloading = this.state.isDownloading;
    this.state.isDownloading = isDownloading;

    // Find active download (with defensive checks)
    const activeDownload = downloadItems.find(item => item && item.active);
    const currentDownloadAppId = activeDownload?.appid || null;

    // Download started
    if (isDownloading && !wasDownloading) {
      console.log("[SystemEvents] Download started");
      this.state.downloadAppId = currentDownloadAppId;
      
      const event: SystemEvent = {
        type: "download_started",
        timestamp: Date.now(),
        app_id: currentDownloadAppId || undefined,
        downloading: true,
      };
      this.emitEvent(event);
    }
    // Download stopped/completed
    else if (!isDownloading && wasDownloading) {
      console.log("[SystemEvents] Download stopped/completed");
      
      // Check if any downloads are completed (with defensive checks)
      const hasCompleted = downloadItems.some(item => item && item.completed);
      
      const event: SystemEvent = {
        type: hasCompleted ? "download_completed" : "download_stopped",
        timestamp: Date.now(),
        app_id: this.state.downloadAppId || undefined,
        downloading: false,
      };
      this.emitEvent(event);
      this.state.downloadAppId = null;
    }
    // Download app changed
    else if (isDownloading && currentDownloadAppId !== this.state.downloadAppId) {
      console.log("[SystemEvents] Download app changed");
      this.state.downloadAppId = currentDownloadAppId;
      
      const event: SystemEvent = {
        type: "download_started",
        timestamp: Date.now(),
        app_id: currentDownloadAppId || undefined,
        downloading: true,
      };
      this.emitEvent(event);
    }
  }

  /**
   * Handle download overview events (progress/rate).
   */
  private handleDownloadOverviewEvent(overview: DownloadOverview) {
    if (!this.state.isDownloading) {
      return;
    }

    const bytesDownloaded = overview.update_bytes_downloaded || 0;
    const bytesToDownload = overview.update_bytes_to_download || 0;
    const bytesPerSecond = overview.update_network_bytes_per_second || 0;

    // Calculate progress percentage
    const progress = bytesToDownload > 0 
      ? Math.round((bytesDownloaded / bytesToDownload) * 100)
      : 0;

    // Convert bytes per second to Mbps
    const rateMbps = bytesPerSecond > 0 
      ? Math.round((bytesPerSecond * 8 / 1000000) * 100) / 100
      : 0;

    console.debug("[SystemEvents] Download progress:", { progress, rateMbps });

    const event: SystemEvent = {
      type: "download_progress",
      timestamp: Date.now(),
      app_id: overview.update_appid || this.state.downloadAppId || undefined,
      progress,
      rate: rateMbps,
      downloading: true,
    };

    this.emitEvent(event);
  }

  /**
   * Handle system suspend events.
   */
  private handleSystemSuspendEvent(progress: SuspendProgress) {
    console.log("[SystemEvents] System suspending:", progress);
    
    const event: SystemEvent = {
      type: "system_suspending",
      timestamp: Date.now(),
    };

    this.emitEvent(event);
  }

  /**
   * Handle system resume events.
   */
  private handleSystemResumeEvent(progress: SuspendProgress) {
    console.log("[SystemEvents] System resuming:", progress);
    
    const event: SystemEvent = {
      type: "system_resuming",
      timestamp: Date.now(),
    };

    this.emitEvent(event);
  }

  /**
   * Handle system shutdown events.
   */
  private handleSystemShutdownEvent(param0: boolean) {
    console.log("[SystemEvents] System shutting down:", param0);
    
    const event: SystemEvent = {
      type: "system_shutting_down",
      timestamp: Date.now(),
    };

    this.emitEvent(event);
  }

  /**
   * Emit an event to the backend.
   */
  private emitEvent(event: SystemEvent) {
    console.log("[SystemEvents] Emitting event:", event);
    
    ingestEvent(event).catch(error => {
      console.error("[SystemEvents] Failed to send event to backend:", error);
    });
  }
}

// Export a singleton instance
export const systemEventManager = new SystemEventManager();
