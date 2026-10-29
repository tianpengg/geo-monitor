from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from internal.server.dependencies import ServerContext


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter()
    database = context.database
    config = context.config

    @router.get("/api/healthz")
    def healthz():
        with database.read() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    @router.get("/downloads/install-collector.sh")
    def installer():
        path = config.project_directory / "scripts" / "install-collector.sh"
        if not path.is_file():
            raise HTTPException(503, "安装文件未就绪")
        return FileResponse(path, media_type="text/x-shellscript", filename="install-collector.sh")

    @router.get("/downloads/collector.tar.gz")
    def bundle():
        from internal.server.downloads import collector_archive

        try:
            archive = collector_archive(config.project_directory)
        except FileNotFoundError:
            raise HTTPException(503, "采集器构建文件未就绪") from None
        return Response(
            archive,
            media_type="application/gzip",
            headers={"Content-Disposition": 'attachment; filename="collector.tar.gz"'},
        )

    @router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown_api(path: str):
        raise HTTPException(404, "接口不存在")

    @router.get("/{path:path}")
    def frontend(path: str):
        root = config.web_directory.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise HTTPException(404, "文件不存在")
        if target.is_file():
            return FileResponse(target)
        index = root / "index.html"
        if index.is_file() and (not Path(path).suffix or path == ""):
            return FileResponse(index)
        raise HTTPException(404, "前端尚未构建或文件不存在")

    return router
