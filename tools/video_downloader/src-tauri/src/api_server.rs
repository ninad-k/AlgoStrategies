use crate::download_manager::DownloadManager;
use crate::models::{DownloadRequest, DownloadResponse, FormatsResponse, HealthResponse, QueueResponse};
use crate::ytdlp::YtDlp;
use axum::extract::{Path, Query, State};
use axum::http::Method;
use axum::response::Json;
use axum::routing::{get, post};
use axum::Router;
use std::collections::HashMap;
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};

pub async fn start_api_server(manager: Arc<DownloadManager>) {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
        .allow_headers(Any);

    let app = Router::new()
        .route("/api/health", get(health))
        .route("/api/download", post(add_download))
        .route("/api/queue", get(get_queue))
        .route("/api/formats", get(get_formats))
        .route("/api/download/{id}/pause", post(pause_download))
        .route("/api/download/{id}/resume", post(resume_download))
        .route("/api/download/{id}/cancel", post(cancel_download))
        .layer(cors)
        .with_state(manager);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:9160")
        .await
        .expect("Failed to bind API server to port 9160");

    axum::serve(listener, app).await.ok();
}

async fn health(State(mgr): State<Arc<DownloadManager>>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        version: "1.0.0".to_string(),
        queue_size: mgr.get_queue_size().await,
    })
}

async fn add_download(
    State(mgr): State<Arc<DownloadManager>>,
    Json(req): Json<DownloadRequest>,
) -> Json<DownloadResponse> {
    let id = mgr
        .add_download(
            &req.url,
            req.title.as_deref(),
            req.page_url.as_deref(),
            req.format_hint.as_deref(),
        )
        .await;

    Json(DownloadResponse {
        id,
        status: "queued".to_string(),
        message: "Download queued".to_string(),
    })
}

async fn get_queue(State(mgr): State<Arc<DownloadManager>>) -> Json<QueueResponse> {
    Json(QueueResponse {
        downloads: mgr.get_downloads().await,
    })
}

async fn get_formats(
    Query(params): Query<HashMap<String, String>>,
) -> Json<serde_json::Value> {
    let url = match params.get("url") {
        Some(u) => u,
        None => {
            return Json(serde_json::json!({"error": "url parameter required"}));
        }
    };

    match YtDlp::extract_info(url).await {
        Ok(info) => Json(serde_json::json!(FormatsResponse {
            title: info.title,
            formats: info.formats,
        })),
        Err(e) => Json(serde_json::json!({"error": e})),
    }
}

async fn pause_download(
    State(mgr): State<Arc<DownloadManager>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    mgr.pause_download(&id).await;
    Json(serde_json::json!({"status": "paused"}))
}

async fn resume_download(
    State(mgr): State<Arc<DownloadManager>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    mgr.resume_download(&id).await;
    Json(serde_json::json!({"status": "downloading"}))
}

async fn cancel_download(
    State(mgr): State<Arc<DownloadManager>>,
    Path(id): Path<String>,
) -> Json<serde_json::Value> {
    mgr.cancel_download(&id).await;
    Json(serde_json::json!({"status": "cancelled"}))
}
