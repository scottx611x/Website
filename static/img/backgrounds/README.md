# Home-page background images

The animated home-page effect (collision / tilt-shift / voronoi) picks a random
image from `manifest.json` on each load.

To add one of your photos:

1. Drop the image file in this folder, e.g. `heron.jpg`.
2. Add its path (relative to `static/img`) to `manifest.json`:

   ```json
   ["fall.jpg", "backgrounds/heron.jpg"]
   ```

3. Commit and deploy.

If `manifest.json` is missing or empty, the site falls back to `fall.jpg`.
