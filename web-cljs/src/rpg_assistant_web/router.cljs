(ns rpg-assistant-web.router
  (:require [domkm.silk :as silk]
            [lambdaisland.uri :as uri]))

(def routes
  (silk/routes
   [[:pages/stat-block-detail [["documents" :document-id "stat-blocks" :stat-block-name]]]
    [:pages/document-chunk [["documents" :document-id "chunks" :chunk-id]]]
    [:pages/stat-blocks [["documents" :document-id "stat-blocks"]]]
    [:pages/document-explorer [["documents" :document-id]]]
    [:pages/campaign-documents [["campaigns" :campaign-id]]]
    [:pages/campaigns []]]))

(defn url->location
  "Convertit un chemin ou une URL en carte :location/* (cf. tutoriel Replicant routing)."
  [routes url]
  (let [uri (cond-> url (string? url) uri/uri)
        path (or (:path uri) "/")]
    (when-let [arrived (silk/arrive routes path)]
      (let [query-params (uri/query-map uri)
            hash-params (some-> uri :fragment uri/query-string->map)]
        (cond-> {:location/page-id (:domkm.silk/name arrived)
                 :location/params (dissoc arrived
                                          :domkm.silk/name
                                          :domkm.silk/pattern
                                          :domkm.silk/routes
                                          :domkm.silk/url)}
          (seq query-params) (assoc :location/query-params query-params)
          (seq hash-params) (assoc :location/hash-params hash-params))))))

(defn location->url
  "Génère l'URL pour une :location/* (routing bidirectionnel via Silk)."
  [routes {:location/keys [page-id params query-params hash-params]}]
  (cond-> (silk/depart routes page-id params)
    (seq query-params)
    (str "?" (uri/map->query-string query-params))

    (seq hash-params)
    (str "#" (uri/map->query-string hash-params))))

(defn essentially-same?
  "Deux locations identiques hors hash (pour replaceState sur query params)."
  [l1 l2]
  (and (= (:location/page-id l1) (:location/page-id l2))
       (= (not-empty (:location/params l1))
          (not-empty (:location/params l2)))
       (= (not-empty (:location/query-params l1))
          (not-empty (:location/query-params l2)))))

(defn query-param
  "Lit un paramètre de requête (clés string ou keyword)."
  [location key]
  (let [params (:location/query-params location {})
        k (if (string? key) key (name key))]
    (or (get params k) (get params (keyword k)))))

(defn current-location []
  (or (url->location routes (.-pathname js/location))
      {:location/page-id :pages/campaigns}))

(defn breadcrumbs
  "Fil d'Ariane sous forme de :location/* pour l'alias :ui/a."
  [location]
  (let [base [{:label "Campagnes"
               :location {:location/page-id :pages/campaigns}}]
        page-id (:location/page-id location)
        params (:location/params location {})]
    (case page-id
      :pages/campaigns base

      :pages/campaign-documents
      (conj base {:label (:campaign-id params)
                  :location location})

      (:pages/document-explorer :pages/document-chunk)
      (let [doc-id (:document-id params)]
        (conj base {:label doc-id
                    :location {:location/page-id :pages/document-explorer
                               :location/params {:document-id doc-id}}}))

      (:pages/stat-blocks :pages/stat-block-detail)
      (let [doc-id (:document-id params)]
        (cond-> (conj base {:label doc-id
                            :location {:location/page-id :pages/document-explorer
                                       :location/params {:document-id doc-id}}})
          true
          (conj {:label "Fiches stats"
                 :location {:location/page-id :pages/stat-blocks
                            :location/params {:document-id doc-id}}})

          (= page-id :pages/stat-block-detail)
          (conj {:label (:stat-block-name params)})))

      (conj base {:label "Page introuvable"}))))
