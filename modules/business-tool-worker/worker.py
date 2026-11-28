import os
import sys
import time
import traceback
from typing import Dict, Any, List

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CORE_PY = os.path.join(ROOT_DIR, "packages", "core", "py")
PROVIDER_PY = os.path.join(ROOT_DIR, "packages", "providers", "local", "py")
for path in [CORE_PY, PROVIDER_PY]:
    if path not in sys.path:
        sys.path.append(path)

from job_queue import LocalJobQueue  # type: ignore
from project_store import load_project, save_project, update_scene_asset  # type: ignore
from paths import ASSETS_DIR, ASSETS_URL_PREFIX  # type: ignore
from local_provider import LocalMediaProvider  # type: ignore

queue = LocalJobQueue()
provider = LocalMediaProvider()


def _asset_path(project_id: str, kind: str, filename: str) -> str:
    return os.path.join(ASSETS_DIR, project_id, kind, filename)


def _asset_url(project_id: str, kind: str, filename: str) -> str:
    return f"{ASSETS_URL_PREFIX}/{project_id}/{kind}/{filename}"


def _append_job_log(project: Dict[str, Any], job: Dict[str, Any], status: str, message: str, asset_url: str | None = None) -> None:
    log = {
        "jobId": job.get("id"),
        "type": job.get("type"),
        "sceneId": job.get("sceneId"),
        "status": status,
        "message": message,
        "assetUrl": asset_url,
    }
    project.setdefault("jobLog", []).append(log)


def _fail_job(job: Dict[str, Any], error_message: str, project: Dict[str, Any] | None = None) -> None:
    attempts = int(job.get("attempts", 0)) + 1
    status = "queued" if attempts < 3 else "failed"
    queue.update_job(
        job["id"],
        {
            "status": status,
            "progress": 0,
            "attempts": attempts,
            "error": {"code": "JOB_FAILED", "message": error_message},
        },
    )
    if project is not None:
        _append_job_log(project, job, status, error_message)
        save_project(project)


def _succeed_job(job: Dict[str, Any], asset_url: str, project: Dict[str, Any] | None = None) -> None:
    queue.update_job(
        job["id"],
        {
            "status": "succeeded",
            "progress": 100,
            "result": {"assetUrl": asset_url},
            "error": None,
        },
    )
    if project is not None:
        _append_job_log(project, job, "succeeded", "ok", asset_url)
        save_project(project)


def _run_image(job: Dict[str, Any], project: Dict[str, Any]) -> str:
    scene_id = job.get("sceneId")
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise RuntimeError("Scene not found")
    out_path = _asset_path(project["id"], "images", f"{scene_id}.png")
    provider.generate_image(project, scene, out_path)
    asset_url = _asset_url(project["id"], "images", f"{scene_id}.png")
    update_scene_asset(project, scene_id, image_asset=asset_url)
    return asset_url


def _run_clip(job: Dict[str, Any], project: Dict[str, Any]) -> str:
    scene_id = job.get("sceneId")
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise RuntimeError("Scene not found")
    out_path = _asset_path(project["id"], "clips", f"{scene_id}.mp4")
    provider.generate_clip(project, scene, out_path)
    asset_url = _asset_url(project["id"], "clips", f"{scene_id}.mp4")
    update_scene_asset(project, scene_id, clip_asset=asset_url)
    return asset_url


def _run_render(job: Dict[str, Any], project: Dict[str, Any]) -> str:
    clip_paths: List[str] = []
    for scene in project.get("scenes", []):
        clip_asset = scene.get("clipAsset")
        if not clip_asset:
            raise RuntimeError("Missing clip for one or more scenes")
        if clip_asset.startswith("/assets/"):
            rel = clip_asset[len("/assets/") :]
        else:
            rel = clip_asset.lstrip("/")
        clip_paths.append(os.path.join(ASSETS_DIR, rel))
    out_path = _asset_path(project["id"], "final", "final.mp4")
    provider.render_final(project, clip_paths, out_path)
    asset_url = _asset_url(project["id"], "final", "final.mp4")
    project["status"] = "rendered"
    return asset_url


def process_job(job: Dict[str, Any]) -> None:
    project = load_project(job["projectId"])
    if project is None:
        _fail_job(job, "Project not found")
        return
    try:
        queue.update_job(job["id"], {"progress": 10, "error": None})
        if job["type"] == "image":
            asset_url = _run_image(job, project)
        elif job["type"] == "clip":
            asset_url = _run_clip(job, project)
        elif job["type"] == "render":
            asset_url = _run_render(job, project)
        else:
            raise RuntimeError("Unknown job type")
        _succeed_job(job, asset_url, project)
    except Exception as exc:
        traceback.print_exc()
        _fail_job(job, str(exc), project)


def main() -> None:
    print("media_worker started")
    while True:
        job = queue.fetch_next()
        if job is None:
            time.sleep(1)
            continue
        process_job(job)


if __name__ == "__main__":
    main()
