FROM registry.git-ce.rwth-aachen.de/ebc/projects/ebc0438_bmwi_bim2sim_ges/bim2sim-coding/environment:dymola

COPY ./bim2sim/plugins/PluginTEASER/requirements.txt ./requirements_teaser.txt

RUN pip install -r ./requirements_teaser.txt

#ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginTEASER/bim2sim_teaser/TEASER/"
