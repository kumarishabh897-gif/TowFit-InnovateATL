from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_camera, get_config
from app.api.schemas import CameraClassification, CameraFrame
from app.config_loader import ConfigStore
from app.services.camera import CameraStore

router = APIRouter(tags=["camera"])


@router.get("/camera/frames", response_model=list[CameraFrame])
def list_frames(camera: CameraStore = Depends(get_camera)) -> list[CameraFrame]:
    """The canned demo frames. These are fixtures, not a live feed."""
    return [CameraFrame(id=f.id, caption=f.caption, image_url=f"/v1/camera/frames/{f.id}/image") for f in camera.list()]


@router.get("/camera/frames/{frame_id}/image")
def frame_image(frame_id: str, camera: CameraStore = Depends(get_camera)) -> FileResponse:
    path = camera.image_path(frame_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown camera frame {frame_id}")
    return FileResponse(path, media_type="image/svg+xml")


@router.post("/camera/frames/{frame_id}/classify", response_model=CameraClassification)
def classify_frame(
    frame_id: str, camera: CameraStore = Depends(get_camera), config: ConfigStore = Depends(get_config)
) -> CameraClassification:
    """Fill a vehicle profile from a canned frame. Labeled SIM: it is a hand-made mapping, not a trained model."""
    vehicle = camera.classify(frame_id, config.snapshot().specs)
    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Unknown camera frame {frame_id}")
    return CameraClassification(frame_id=frame_id, vehicle=vehicle)
