"""
Sync Manager and Model Downloader Integrator (T205)
Integrates edge sync manager with model downloader for automatic model updates
"""
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SyncModelIntegrator:
    """
    Integrates Sync Manager with Model Downloader

    Responsibilities:
    - Periodically checks for new model versions during sync cycles
    - Downloads and deploys new ONNX models automatically
    - Validates model checksums before deployment
    - Rolls back on model failures

    Implements edge-first autonomous operation with cloud model updates
    """

    def __init__(
        self,
        model_downloader,
        deployment_manager,
        cloud_api_url: str,
        check_interval_hours: float = 6.0,
        auto_deploy: bool = True,
    ):
        """
        Initialize integrator

        Args:
            model_downloader: ModelDownloader instance for fetching models
            deployment_manager: DeploymentManager for model deployment
            cloud_api_url: Cloud API base URL
            check_interval_hours: How often to check for new models
            auto_deploy: Whether to automatically deploy new models
        """
        self.model_downloader = model_downloader
        self.deployment_manager = deployment_manager
        self.cloud_api_url = cloud_api_url
        self.check_interval_hours = check_interval_hours
        self.auto_deploy = auto_deploy

        self._last_check: Optional[datetime] = None
        self._current_model_version: Optional[str] = None

        logger.info(
            f"SyncModelIntegrator initialized: "
            f"check_interval={check_interval_hours}h, auto_deploy={auto_deploy}"
        )

    async def check_and_update_models(self) -> Dict[str, Any]:
        """
        Check for model updates and deploy if available

        Returns:
            Dict with check results:
            - checked: bool
            - new_model_available: bool
            - deployed: bool
            - model_version: str (if updated)
            - error: str (if failed)
        """
        result = {
            "checked": False,
            "new_model_available": False,
            "deployed": False,
            "model_version": None,
            "error": None,
        }

        # Check if it's time to check for updates
        now = datetime.utcnow()
        if self._last_check:
            time_since_check = now - self._last_check
            if time_since_check < timedelta(hours=self.check_interval_hours):
                logger.debug(
                    f"Skipping model check, last check was {time_since_check} ago"
                )
                return result

        try:
            self._last_check = now
            result["checked"] = True

            # Check for new model version
            logger.info("Checking cloud for model updates...")
            latest_info = await self.model_downloader.get_latest_model_info()

            if not latest_info:
                logger.debug("No model info returned from cloud")
                return result

            latest_version = latest_info.get("version")
            if not latest_version:
                return result

            # Compare with current version
            if latest_version == self._current_model_version:
                logger.debug(f"Model version {latest_version} is already deployed")
                return result

            logger.info(
                f"New model version available: {latest_version} "
                f"(current: {self._current_model_version})"
            )
            result["new_model_available"] = True
            result["model_version"] = latest_version

            if not self.auto_deploy:
                logger.info("Auto-deploy disabled, skipping deployment")
                return result

            # Download new model
            model_path = await self.model_downloader.download_model(
                latest_info.get("model_id") or latest_version
            )

            if not model_path:
                result["error"] = "Failed to download model"
                return result

            # Validate checksum
            expected_checksum = latest_info.get("checksum")
            if expected_checksum:
                valid = await self.model_downloader.validate_checksum(
                    model_path, expected_checksum
                )
                if not valid:
                    result["error"] = "Model checksum validation failed"
                    logger.error(f"Checksum validation failed for {model_path}")
                    return result

            # Deploy model
            success = await self.deployment_manager.deploy_model(
                model_path,
                version=latest_version,
                metadata=latest_info.get("metadata", {}),
            )

            if success:
                self._current_model_version = latest_version
                result["deployed"] = True
                logger.info(f"Successfully deployed model version {latest_version}")
            else:
                result["error"] = "Model deployment failed"
                logger.error(f"Failed to deploy model {latest_version}")

            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error during model update check: {e}", exc_info=True)
            return result

    def set_current_version(self, version: str):
        """Set the current model version (for initialization)"""
        self._current_model_version = version
        logger.info(f"Current model version set to {version}")

    def force_check(self):
        """Force next check to happen immediately"""
        self._last_check = None
        logger.debug("Forced next model check")


async def run_model_sync_loop(
    integrator: SyncModelIntegrator,
    interval_seconds: int = 3600,
    stop_event: Optional[asyncio.Event] = None,
):
    """
    Run continuous model sync loop

    Args:
        integrator: SyncModelIntegrator instance
        interval_seconds: Check interval in seconds
        stop_event: Optional event to stop the loop
    """
    logger.info(f"Starting model sync loop (interval: {interval_seconds}s)")

    while True:
        if stop_event and stop_event.is_set():
            logger.info("Model sync loop stopped")
            break

        try:
            result = await integrator.check_and_update_models()

            if result.get("deployed"):
                logger.info(
                    f"Model sync: deployed version {result['model_version']}"
                )
            elif result.get("error"):
                logger.warning(f"Model sync error: {result['error']}")

        except Exception as e:
            logger.error(f"Error in model sync loop: {e}", exc_info=True)

        # Wait for next check
        try:
            if stop_event:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval_seconds
                )
                break
            else:
                await asyncio.sleep(interval_seconds)
        except asyncio.TimeoutError:
            continue


def integrate_sync_with_model_downloader(
    sync_manager,
    model_downloader,
    deployment_manager,
    cloud_api_url: str,
    **integrator_kwargs
) -> SyncModelIntegrator:
    """
    Factory function to create and attach integrator to sync manager

    Args:
        sync_manager: SyncManager instance
        model_downloader: ModelDownloader instance
        deployment_manager: DeploymentManager instance
        cloud_api_url: Cloud API base URL
        **integrator_kwargs: Additional integrator configuration

    Returns:
        SyncModelIntegrator instance
    """
    integrator = SyncModelIntegrator(
        model_downloader=model_downloader,
        deployment_manager=deployment_manager,
        cloud_api_url=cloud_api_url,
        **integrator_kwargs
    )

    # If sync_manager has a post-sync hook, register model check
    if hasattr(sync_manager, 'add_post_sync_hook'):
        async def model_check_hook():
            await integrator.check_and_update_models()

        sync_manager.add_post_sync_hook(model_check_hook)
        logger.info("Model check hook registered with sync manager")

    return integrator
