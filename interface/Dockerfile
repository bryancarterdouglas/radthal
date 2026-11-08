# Pages web Radthal (noeud, tableau de bord, mempool, portefeuille, horodatage).
# Python seul, aucune bibliotheque a installer. Le conteneur partage le reseau du noeud
# (voir docker-compose.yml) : il lui parle en local et lit son cookie RPC en lecture seule.
FROM python:3.12-alpine
LABEL org.opencontainers.image.source="https://github.com/bryancarterdouglas/radthal" \
      org.opencontainers.image.description="Pages web Radthal : noeud, tableau de bord, mempool, portefeuille, horodatage" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY ui_node.py ui_dashboard.py ui_wallet.py ui_horodatage.py launcher.py hub.py /app/
# /state : la liste des horodatages (volume, garde entre deux mises a jour). Meme utilisateur (1000) que le noeud.
RUN mkdir /state && chown 1000:1000 /state
USER 1000:1000
VOLUME /state
CMD ["python", "/app/launcher.py"]
