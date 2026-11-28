/**
 * 1-Click Undo Ring Buffer for SmartSchedule UI (`M6` Wave 2A).
 *
 * Maintains a bounded deep-cloned history of workspace scheduling state
 * (`commitments`, `tasks`, `pinnedBlocks`, `completedBlocks`, `currentSchedule`)
 * so accidental drags, deletions, or assistant re-plans can be reverted in one click.
 */

export const MAX_UNDO_ENTRIES = 10;

const _undoBuffer = [];

function _deepClone(value) {
  if (value === null || value === undefined) return value;
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(value);
    } catch {
      // Fallback for non-structured-cloneable plain JSON objects
    }
  }
  return JSON.parse(JSON.stringify(value));
}

function _captureSnapshot(sourceState) {
  return _deepClone({
    commitments: sourceState?.commitments || {},
    tasks: Array.isArray(sourceState?.tasks) ? sourceState.tasks : [],
    pinnedBlocks: Array.isArray(sourceState?.pinnedBlocks) ? sourceState.pinnedBlocks : [],
    completedBlocks: sourceState?.completedBlocks && typeof sourceState.completedBlocks === "object"
      ? sourceState.completedBlocks
      : {},
    currentSchedule: sourceState?.currentSchedule || null,
  });
}

/**
 * Push a deep-cloned workspace snapshot into the undo ring buffer (capped at 10 entries).
 *
 * @param {object} targetState - Central UI state object
 * @param {string} actionLabel - Human-readable Vietnamese description of the mutation
 * @returns {{ snapshot: object, actionLabel: string, timestamp: number }}
 */
export function pushUndoSnapshot(targetState, actionLabel = "Thay đổi lịch trình") {
  const entry = {
    snapshot: _captureSnapshot(targetState),
    actionLabel: String(actionLabel || "Thay đổi lịch trình"),
    timestamp: Date.now(),
  };

  _undoBuffer.push(entry);
  while (_undoBuffer.length > MAX_UNDO_ENTRIES) {
    _undoBuffer.shift();
  }
  return entry;
}

/**
 * Pop the most recent snapshot and restore it onto `targetState` (when provided).
 *
 * @param {object} [targetState] - Central UI state object to mutate back in place
 * @returns {{ snapshot: object, actionLabel: string } | null}
 */
export function popUndoSnapshot(targetState) {
  if (_undoBuffer.length === 0) return null;
  const entry = _undoBuffer.pop();
  const restored = _deepClone(entry.snapshot);

  if (targetState && typeof targetState === "object") {
    targetState.commitments = restored.commitments;
    targetState.tasks = restored.tasks;
    targetState.pinnedBlocks = restored.pinnedBlocks;
    targetState.completedBlocks = restored.completedBlocks;
    targetState.currentSchedule = restored.currentSchedule;
    if (targetState.schedulesBySolver && typeof targetState.schedulesBySolver === "object") {
      targetState.schedulesBySolver = {};
      if (targetState.activeSolver && restored.currentSchedule) {
        targetState.schedulesBySolver[targetState.activeSolver] = restored.currentSchedule;
      }
    }
    targetState.benchmarkData = null;
    targetState.weightsData = null;
    targetState.overloadPreview = null;
  }

  return {
    snapshot: restored,
    actionLabel: entry.actionLabel,
  };
}

/**
 * Return true if at least one undo snapshot is available.
 * @returns {boolean}
 */
export function canUndo() {
  return _undoBuffer.length > 0;
}

/**
 * Peek metadata for the top undo entry without popping it.
 * @returns {{ actionLabel: string, timestamp: number } | null}
 */
export function peekUndoSnapshot() {
  if (_undoBuffer.length === 0) return null;
  const top = _undoBuffer[_undoBuffer.length - 1];
  return { actionLabel: top.actionLabel, timestamp: top.timestamp };
}

/**
 * Return current number of stored undo snapshots.
 * @returns {number}
 */
export function getUndoCount() {
  return _undoBuffer.length;
}

/**
 * Clear all undo snapshots (e.g. when switching workspace or starting fresh).
 */
export function clearUndoHistory() {
  _undoBuffer.length = 0;
}
