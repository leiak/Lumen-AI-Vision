from prometheus_client import Counter


EDGE_EVENTS = Counter(
    "vr_edge_events_total",
    "Accepted edge events",
    ["camera_id", "area_id", "risk_level"],
)
EDGE_KEYFRAMES = Counter(
    "vr_edge_keyframes_total",
    "Uploaded or accepted keyframes",
    ["frame_role"],
)
EDGE_UPLOAD_FAILURES = Counter(
    "vr_edge_upload_failures_total",
    "Failed edge keyframe uploads",
    ["reason"],
)
TASK_UPDATES = Counter(
    "vr_task_updates_total",
    "Task status updates",
    ["status", "result"],
)
REVIEWS = Counter(
    "vr_reviews_total",
    "Event review results",
    ["result"],
)
NOTIFICATION_READS = Counter(
    "vr_notification_reads_total",
    "Notifications marked as read",
    ["mode"],
)
