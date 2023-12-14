FROM registry.git.rwth-aachen.de/ebc/ebc_intern/dymola-docker:Dymola_2022

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH /opt/conda/bin:$PATH

RUN apt-get update --fix-missing && \
    apt-get install -y wget bzip2 ca-certificates curl git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    /opt/conda/bin/conda clean -tipsy && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate base" >> ~/.bashrc

ENV TINI_VERSION v0.16.1
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/bin/tini
RUN chmod +x /usr/bin/tini

ENTRYPOINT [ "/usr/bin/tini", "--" ]
CMD [ "/bin/bash" ]
########################################################


########################################################
WORKDIR /bim2sim-coding

RUN apt-get --allow-releaseinfo-change update
RUN apt-get -y install unzip
RUN apt-get -y install libgl-dev

# Copy files
COPY ./requirements.txt .

RUN 	conda create -n env python=3.10
RUN		conda update -n base -c defaults conda
RUN 	echo "source activate env" > ~/.bashrc
ENV 	PATH /opt/conda/envs/env/bin:$PATH
SHELL 	["conda", "run", "-n", "env", "/bin/bash", "-c"]

# install needed packages

RUN pip install --default-timeout=100 -r ./requirements.txt

# install needed packages

## install pythonocc via conda
RUN /opt/conda/bin/conda install --yes --freeze-installed \
	    -c dlr-sc pythonocc-core=7.4.1 \
	    nomkl \
	&& /opt/conda/bin/conda clean -afy \
	&& find /opt/conda/ -follow -type f -name '*.a' -delete \
	&& find /opt/conda/ -follow -type f -name '*.pyc' -delete \
	&& find /opt/conda/ -follow -type f -name '*.js.map' -delete


# Set Pythonpath
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginEnergyPlus"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginCFD"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginAixLib"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginHKESim"
ENV PYTHONPATH "${PYTHONPATH}:/bim2sim-coding/bim2sim/plugins/PluginTEASER"

########################################################


