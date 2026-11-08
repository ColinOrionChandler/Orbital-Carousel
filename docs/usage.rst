
User guide
==========


Orbital Carousel plots small-body orbits in heliocentric or planet co-rotating
reference frames. It is a standalone version of the old ``coc_tools``
``corotating.py`` plotting script, with an installable command-line interface and
configurable output products.


Install
-------


Requires Python 3.11 or newer. From this checkout:


.. code-block:: bash

   python -m pip install -e .


For tests:


.. code-block:: bash

   python -m pip install -e ".[test]"


For the optional ASSIST long-span integrator:


.. code-block:: bash

   python -m pip install -e ".[integrator]"



Command Line
------------


The main command is ``orbital-carousel``. The older ``corotating-carousel`` name is
also installed as a compatibility alias:


.. code-block:: bash

   orbital-carousel "2015 DD349"


By default this writes both PDF and PNG plots into a directory named after the
object, with spaces replaced by underscores and ``/`` replaced by ``+``.

Common options:


.. code-block:: bash

   orbital-carousel "C/2014 OG392" --planets auto --format png
   orbital-carousel "2019 OE31" --planets auto --format png
   orbital-carousel "2000 OG44" --frame heliocentric --planets Venus,Earth,Mars,Jupiter
   orbital-carousel "2010 RJ226" --frame-body Saturn --figsize 8 8 --output-dir plots
   orbital-carousel "2015 DD349" --frame-body Jupiter --frame-body Saturn --format png
   orbital-carousel "2015 DD349" --exclude-planet Mercury --exclude-planet Venus
   orbital-carousel "2025 NN80" --ephemeris assist --format png


From a source checkout, the CLI file can also show help directly:


.. code-block:: bash

   python src/orbital_carousel/cli.py -h



Epoch Defaults
~~~~~~~~~~~~~~


By default, missing epoch settings are scaled from the target's Horizons orbital
period. With no epoch options, the stop date is today, the start date is at least
20 target orbits earlier, and the step size uses 120 samples per orbit. This is
intended to make long-period objects such as ``2019 OE31`` show many full cycles
without hand-tuning a centuries-long date range.

You can tune the derived range with ``--orbits`` and ``--samples-per-orbit``, or
override individual fields with ``--start``, ``--stop``, or ``--step``. To use the old
fixed missing-epoch defaults of ``2000-01-01`` to ``2030-01-01`` at ``30d``, pass
``--no-auto-epochs``:


.. code-block:: bash

   orbital-carousel "2019 OE31" --no-auto-epochs


Calendar dates use astronomical year numbering, so year ``0000`` is 1 BCE and
``-0001`` is 2 BCE. ``--start``, ``--stop``, and ``--integration-epoch`` also accept
``JD<number>`` TDB Julian Dates. ASSIST supports fixed day/hour/minute steps,
calendar month/year steps, and positive unitless interval counts.

``--planets auto`` first queries the target, finds its maximum heliocentric
distance across the requested epochs, and plots planets through the next planet
outside that distance. Objects beyond Neptune keep all supported planets.

``--frame-body`` controls which planet is fixed on the positive x-axis in
co-rotating plots. It defaults to Jupiter, and accepts repeated or
comma-separated values when you want multiple reference-frame outputs from one
run:


.. code-block:: bash

   orbital-carousel "2015 DD349" --frame-body Jupiter,Saturn --format png



ASSIST Long-Span Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~


The default ``--ephemeris auto`` tries Horizons first. If Horizons reports
that the target, a plotted planet, or a co-rotating frame body is outside its
coverage, Orbital Carousel retries the entire requested interval with ASSIST.
Use ``--ephemeris horizons`` to require Horizons or ``--ephemeris assist`` to
start directly with the long-span backend.

ASSIST seeds the target from one Horizons barycentric ICRF state and propagates
it locally with ASSIST/REBOUND IAS15. Planet and frame-body positions come from
the same local DE441 ephemeris, allowing plots outside Horizons' per-body
coverage windows.

ASSIST needs the extended DE441 planet ephemeris and the 16-asteroid kernel,
which total more than 3 GB. Place them in ``~/.cache/orbital-carousel/assist``
or set ``ASSIST_DIR`` to their directory:


.. code-block:: bash

   mkdir -p /path/to/assist-data
   curl https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/linux_m13000p17000.441 \
     -o /path/to/assist-data/linux_m13000p17000.441
   curl https://ssd.jpl.nasa.gov/ftp/eph/small_bodies/asteroids_de441/sb441-n16.bsp \
     -o /path/to/assist-data/sb441-n16.bsp
   export ASSIST_DIR=/path/to/assist-data

   orbital-carousel "2025 NN80" --ephemeris assist --format png


Use ``--assist-data-dir`` to override ``ASSIST_DIR`` for one run and
``--integration-epoch`` to choose the Horizons seed-state epoch. ASSIST output
filenames include ``_assist_`` and figures identify the seed epoch and DE441/n16
model. These are nominal trajectories: v1 does not propagate the fitted orbit's
covariance or retrieve cometary non-gravitational parameters.


Orbit animations
~~~~~~~~~~~~~~~~

Use ``--format mp4`` to save a growing-path animation. Install FFmpeg with the
``libx264`` encoder and make it available on your PATH or through Matplotlib's
``animation.ffmpeg_path`` setting. To reproduce the 2013 BU1 movie, run:

.. code-block:: bash

   orbital-carousel "2013 BU1" --start 1762-11-29 --stop 2026-11-08 --step 41d \
       --ephemeris assist --integration-epoch 2026-11-08 --frame-body Jupiter \
       --planets all --format mp4 --figsize 12 9 --fps 24 --duration 30

The axes stay fixed while the target and planet markers advance through the
sampled TDB epochs. The default playback rate is 24 frames per second and the
default maximum duration is 30 seconds. Short trajectories show every sample
and finish sooner. For longer trajectories the renderer selects samples nearest
evenly spaced times and draws the full path between displayed markers. A
multi-sample movie needs enough time for at least two frames at the chosen rate.

Repeat ``--format`` to write a movie and still plots using the same vectors,
for example ``--format png --format mp4``. The Python equivalent is
``plot_orbit("2013 BU1", formats=("png", "mp4"), fps=24, duration=30)``.


Python API
----------



.. code-block:: python

   from orbital_carousel import plot_orbit

   paths = plot_orbit(
       "2025 NN80",
       frame="corotating",
       frame_body=("Jupiter", "Saturn"),
       planets="auto",
       formats=("pdf", "png"),
       ephemeris="assist",
       assist_data_dir="/path/to/assist-data",
   )


``plot_orbit()`` returns the paths it wrote. The supported planets are Mercury
through Neptune. The Python API uses the same automatic backend selection and orbit-scaled epoch
defaults as the CLI unless ``auto_epochs=False`` is passed.
