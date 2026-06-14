(ns rpg-assistant-web.events
  (:require [clojure.string :as str]
            [clojure.walk :as walk]
            [rpg-assistant-web.api :as api]
            [rpg-assistant-web.router :as router]
            [rpg-assistant-web.state :as state]
            [rpg-assistant-web.utils.pdf-path :as pdf-path]))

(defonce ^:private !render (atom nil))

(declare sync-route! load-chunks!)

(defn set-render! [f]
  (reset! !render f))

(defn- render! []
  (when-let [f @!render]
    (f)))

(defn- narrow-screen? []
  (.matches (js/window.matchMedia "(max-width: 900px)")))

(defn- interpolate-actions [dom-event actions]
  (walk/postwalk
   (fn [x]
     (case x
       :event/target.value (.. dom-event -target -value)
       x))
   actions))

(defn- navigate-url! [url replace?]
  (if replace?
    (.replaceState js/history nil "" url)
    (.pushState js/history nil "" url)))

(defn navigate-location!
  ([location] (navigate-location! location false))
  ([location replace?]
   (let [url (router/location->url router/routes location)]
     (navigate-url! url replace?)
     (swap! state/store assoc :location location)
     (sync-route!)
     (render!))))

(defn- section-id-from-location [location sections]
  (let [query-section (router/query-param location "section")
        valid? (some #(= (:id %) query-section) sections)]
    (when (and query-section valid?) query-section)))

(defn- default-section-id [sections]
  (:id (first sections)))

(defn- ensure-section! [location sections]
  (let [section-id (or (section-id-from-location location sections)
                       (default-section-id sections))]
    (when (and section-id
               (not= section-id (router/query-param location "section")))
      (navigate-location!
       (assoc-in location [:location/query-params "section"] section-id)
       true))))

(defn load-campaigns! []
  (swap! state/store assoc
         :campaigns-loading? true
         :campaigns-error nil)
  (render!)
  (-> (api/fetch-json "/campaigns")
      (.then
       (fn [result]
         (if (:ok result)
           (swap! state/store assoc
                  :campaigns (:data result)
                  :campaigns-loading? false
                  :campaigns-error nil)
           (swap! state/store assoc
                  :campaigns-loading? false
                  :campaigns-error (or (:error result) "Erreur réseau")))
         (render!)))))

(defn- load-campaign-documents! [campaign-id]
  (swap! state/store assoc-in [:documents-by-campaign campaign-id]
         {:documents nil :summary nil :loading? true :error nil})
  (render!)
  (-> (js/Promise.all
       #js [(api/fetch-json (str "/campaigns/" campaign-id "/documents"))
            (api/fetch-json (str "/campaigns/" campaign-id "/summary"))])
      (.then
       (fn [results]
         (let [docs-result (aget results 0)
               summary-result (aget results 1)]
           (if (and (:ok docs-result) (:ok summary-result))
             (swap! state/store assoc-in [:documents-by-campaign campaign-id]
                    {:documents (:data docs-result)
                     :summary (:data summary-result)
                     :loading? false
                     :error nil})
             (swap! state/store assoc-in [:documents-by-campaign campaign-id]
                    {:documents nil :summary nil :loading? false
                     :error (or (:error docs-result) (:error summary-result) "Erreur réseau")})))
         (render!)))))

(defn- load-sections! [document-id]
  (swap! state/store assoc-in [:explorer-by-document document-id]
         (merge (state/explorer-state @state/store document-id)
                {:loading? true :error nil}))
  (render!)
  (-> (api/fetch-json (str "/documents/" document-id "/sections"))
      (.then
       (fn [result]
         (if (:ok result)
           (let [sections (:data result)
                 location (:location @state/store)]
             (swap! state/store assoc-in [:explorer-by-document document-id]
                    (merge (state/explorer-state @state/store document-id)
                           {:sections sections :loading? false :error nil}))
             (ensure-section! location sections)
             (when-let [section-id (or (section-id-from-location (:location @state/store) sections)
                                       (default-section-id sections))]
               (load-chunks! document-id section-id)))
           (swap! state/store assoc-in [:explorer-by-document document-id]
                  (merge (state/explorer-state @state/store document-id)
                         {:loading? false
                          :error (or (:error result) "Erreur réseau")})))
         (render!)))))

(defn load-chunks!
  [document-id section-id]
  (when (and document-id section-id)
    (-> (api/fetch-json
         (str "/documents/" document-id "/chunks"
              "?section_id=" (js/encodeURIComponent section-id)
              "&limit=50"))
        (.then
         (fn [result]
           (if (:ok result)
             (swap! state/store assoc-in [:explorer-by-document document-id :chunks]
                    (:data result))
             (swap! state/store assoc-in [:explorer-by-document document-id :error]
                    (or (:error result) "Erreur réseau")))
           (render!))))))

(defn- load-chunk! [chunk-id document-id]
  (swap! state/store assoc-in [:explorer-by-document document-id :chunk] nil)
  (render!)
  (-> (api/fetch-json (str "/chunks/" chunk-id))
      (.then
       (fn [result]
         (if (:ok result)
           (swap! state/store assoc-in [:explorer-by-document document-id :chunk]
                  (:data result))
           (swap! state/store assoc-in [:explorer-by-document document-id :error]
                  (or (:error result) "Chunk introuvable")))
         (render!)))))

(defn- load-stat-blocks! [document-id]
  (swap! state/store assoc-in [:stat-blocks-by-document document-id]
         {:entries nil :loading? true :error nil})
  (render!)
  (-> (api/fetch-json (str "/documents/" document-id "/stat-blocks"))
      (.then
       (fn [result]
         (if (:ok result)
           (swap! state/store assoc-in [:stat-blocks-by-document document-id]
                  {:entries (:data result) :loading? false :error nil})
           (swap! state/store assoc-in [:stat-blocks-by-document document-id]
                  {:entries nil :loading? false
                   :error (or (:error result) "Erreur réseau")}))
         (render!)))))

(defn- load-stat-block-detail! [document-id name]
  (let [key [document-id name]]
    (swap! state/store assoc-in [:stat-block-detail-by-key key]
           {:detail nil :candidates nil :loading? true :error nil})
    (render!)
    (-> (api/fetch-json
         (str "/documents/" document-id "/stat-blocks/"
              (js/encodeURIComponent name)))
        (.then
         (fn [result]
           (if (:ok result)
             (swap! state/store assoc-in [:stat-block-detail-by-key key]
                    {:detail (:data result) :candidates nil
                     :loading? false :error nil})
             (let [status (:status result)
                   body (:body result)]
               (if (= status 422)
                 (swap! state/store assoc-in [:stat-block-detail-by-key key]
                        {:detail nil
                         :candidates (:candidates body)
                         :loading? false
                         :error (or (:error body)
                                    "Plusieurs fiches correspondent à ce nom.")})
                 (swap! state/store assoc-in [:stat-block-detail-by-key key]
                        {:detail nil :candidates nil :loading? false
                         :error (or (:error result) "Fiche introuvable")}))))
           (render!))))))

(defn load-pdf-page!
  [document-id page]
  (let [stored-path (pdf-path/load-path document-id)]
    (swap! state/store assoc-in [:pdf-by-document document-id]
           (merge (state/pdf-state @state/store document-id)
                  {:loading? true :error nil :needs-override? false
                   :draft-path (or stored-path "")}))
    (render!)
    (-> (js/Promise.all
         #js [(api/fetch-json (str "/documents/" document-id "/pages/" page))
              (api/fetch-json (str "/documents/" document-id "/pages/" page "/blocks"))])
        (.then
         (fn [results]
           (let [meta-result (aget results 0)
                 blocks-result (aget results 1)]
             (cond
               (and (:ok meta-result) (:ok blocks-result))
               (swap! state/store assoc-in [:pdf-by-document document-id]
                      (merge (state/pdf-state @state/store document-id)
                             {:meta (:data meta-result)
                              :blocks (:data blocks-result)
                              :loading? false :error nil}))

               (= "pdf_not_found" (get-in meta-result [:body :code]))
               (swap! state/store assoc-in [:pdf-by-document document-id]
                      (merge (state/pdf-state @state/store document-id)
                             {:loading? false :needs-override? true
                              :error (:error meta-result)}))

               :else
               (swap! state/store assoc-in [:pdf-by-document document-id]
                      (merge (state/pdf-state @state/store document-id)
                             {:loading? false
                              :error (or (:error meta-result)
                                         (:error blocks-result)
                                         "Erreur de chargement")}))))
           (render!))))))

(defn sync-route! []
  (let [{:location/keys [page-id params query-params]} (:location @state/store)
        document-id (:document-id params)
        campaign-id (:campaign-id params)
        chunk-id (:chunk-id params)
        stat-name (:stat-block-name params)]
    (case page-id
      :pages/campaigns
      (when (nil? (:campaigns @state/store))
        (load-campaigns!))

      :pages/campaign-documents
      (when campaign-id
        (let [current (state/documents-state @state/store campaign-id)]
          (when (nil? (:documents current))
            (load-campaign-documents! campaign-id))))

      (:pages/document-explorer :pages/document-chunk)
      (when document-id
        (let [explorer (state/explorer-state @state/store document-id)]
          (when (nil? (:sections explorer))
            (load-sections! document-id))
          (when (and chunk-id (= page-id :pages/document-chunk))
            (load-chunk! chunk-id document-id))
          (when (and (not chunk-id) (:sections explorer))
            (when-let [section-id (router/query-param {:location/query-params query-params} "section")]
              (load-chunks! document-id section-id)))))

      :pages/stat-blocks
      (when document-id
        (let [sb (state/stat-blocks-state @state/store document-id)]
          (when (nil? (:entries sb))
            (load-stat-blocks! document-id))))

      :pages/stat-block-detail
      (when (and document-id stat-name)
        (let [detail (state/stat-block-detail-state @state/store document-id stat-name)]
          (when (nil? (:detail detail))
            (load-stat-block-detail! document-id stat-name))))

      nil)))

(defn show-pdf-source! [page highlight]
  (swap! state/store assoc :pdf-panel
         {:open true
          :page page
          :highlight highlight
          :mobile-open? (narrow-screen?)})
  (let [document-id (get-in @state/store [:location :location/params :document-id])]
    (when document-id
      (load-pdf-page! document-id page)))
  (render!))

(defn close-pdf-panel! []
  (swap! state/store assoc :pdf-panel state/initial-pdf-panel)
  (render!))

(defn pdf-image-loaded! [width height]
  (let [document-id (get-in @state/store [:location :location/params :document-id])]
    (swap! state/store assoc-in [:pdf-by-document document-id]
           (merge (state/pdf-state @state/store document-id)
                  {:image-width width :image-height height}))
    (render!)))

(defn pdf-image-error! []
  (let [document-id (get-in @state/store [:location :location/params :document-id])]
    (swap! state/store assoc-in [:pdf-by-document document-id]
           (merge (state/pdf-state @state/store document-id)
                  {:needs-override? true
                   :error "Impossible de charger l'image PDF. Indiquez le chemin absolu du fichier source."}))
    (render!)))

(defn dispatch-event! [replicant-data actions]
  (let [dom-event (:replicant/dom-event replicant-data)
        actions (interpolate-actions dom-event actions)]
    (doseq [action actions]
      (case (first action)
        :load-campaigns (load-campaigns!)
        :retry-campaigns (load-campaigns!)

        :load-campaign-documents
        (when-let [campaign-id (get-in @state/store [:location :location/params :campaign-id])]
          (load-campaign-documents! campaign-id))

        :set-stat-block-filter
        (do (swap! state/store assoc :stat-block-filter (nth action 1))
            (render!))

        :set-mobile-tab
        (do (swap! state/store assoc :mobile-tab (keyword (nth action 1)))
            (render!))

        :select-section
        (let [section-id (nth action 1)
              location (:location @state/store)
              params (:location/params location {})
              doc-id (:document-id params)
              new-loc (-> location
                          (assoc :location/page-id :pages/document-explorer)
                          (assoc :location/params {:document-id doc-id})
                          (assoc :location/query-params {"section" section-id}))]
          (swap! state/store assoc :mobile-tab :content)
          (navigate-location! new-loc true))

        :show-pdf-source
        (show-pdf-source! (nth action 1) (nth action 2))

        :close-pdf-panel (close-pdf-panel!)

        :set-pdf-draft-path
        (let [document-id (get-in @state/store [:location :location/params :document-id])]
          (swap! state/store assoc-in [:pdf-by-document document-id :draft-path]
                 (nth action 1))
          (render!))

        :save-pdf-path
        (let [document-id (get-in @state/store [:location :location/params :document-id])
              draft (get-in @state/store [:pdf-by-document document-id :draft-path])]
          (pdf-path/save-path! document-id draft)
          (swap! state/store assoc-in [:pdf-by-document document-id :needs-override?] false)
          (when-let [page (get-in @state/store [:pdf-panel :page])]
            (load-pdf-page! document-id page))
          (render!))

        :clear-pdf-path
        (let [document-id (get-in @state/store [:location :location/params :document-id])]
          (pdf-path/clear-path! document-id)
          (swap! state/store assoc-in [:pdf-by-document document-id :draft-path] "")
          (render!))

        :pdf-image-loaded
        (let [document-id (get-in @state/store [:location :location/params :document-id])
              width (nth action 1)
              height (nth action 2)]
          (swap! state/store assoc-in [:pdf-by-document document-id]
                 (merge (state/pdf-state @state/store document-id)
                        {:image-width width :image-height height}))
          (render!))

        :pdf-image-error
        (let [document-id (get-in @state/store [:location :location/params :document-id])]
          (swap! state/store assoc-in [:pdf-by-document document-id]
                 (merge (state/pdf-state @state/store document-id)
                        {:needs-override? true
                         :error "Impossible de charger l'image PDF. Indiquez le chemin absolu du fichier source."}))
          (render!))

        nil))))

(defn on-location-changed! [location replace?]
  (swap! state/store assoc
         :location location
         :mobile-tab :content)
  (when (not= :pages/document-chunk (:location/page-id location))
    (when-let [doc-id (get-in location [:location/params :document-id])]
      (swap! state/store assoc-in [:explorer-by-document doc-id :chunk] nil)))
  (sync-route!)
  (render!))
