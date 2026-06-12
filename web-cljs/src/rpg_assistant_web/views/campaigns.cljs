(ns rpg-assistant-web.views.campaigns)

(defn- loading-view []
  [:main.page
   [:div.loading
    [:p "Chargement des campagnes…"]]])

(defn- error-view [message]
  [:main.page
   [:div.error-box
    [:p message]
    [:button {:on {:click [[:retry-campaigns]]}} "Réessayer"]]])

(defn- empty-view []
  [:main.page
   [:div.state-box
    [:h2 "Aucune campagne importée"]
    [:p.muted "Importez un PDF via la CLI :"]
    [:pre {:style {:text-align "left" :overflow "auto"}}
     "uv run rpg-ingest raw extract <fichier.pdf> \\\n  --campaign-id momie --game-system cof2"]]])

(defn- campaign-card [campaign]
  (let [id (or (:id campaign) (:campaign-id campaign))
        title (or (:title campaign) id)]
    [:ui/a.card {:key id
                 :ui/location {:location/page-id :pages/campaign-documents
                                :location/params {:campaign-id id}}}
     [:h3 title]
     [:p.muted
      (str (:document_count campaign 0) " document(s)")
      (when-let [gs (:game_system campaign)]
        (str " · " gs))]]))

(defn campaigns-view [{:keys [campaigns campaigns-loading? campaigns-error]}]
  (cond
    campaigns-loading? (loading-view)
    campaigns-error (error-view campaigns-error)
    (empty? campaigns) (empty-view)
    :else
    [:main.page
     [:h2 "Campagnes"]
     [:div.card-grid
      (map campaign-card campaigns)]]))
