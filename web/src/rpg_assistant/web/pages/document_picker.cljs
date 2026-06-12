(ns rpg-assistant.web.pages.document-picker
  (:require ["react-router-dom" :refer [Link useParams]]
            [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.api :as api]
            [rpg-assistant.web.components.common :refer [loading-state error-state empty-state]]))

(defn- fetch-documents! [campaign-id set-documents! set-summary! set-error! set-loading!]
  (when (seq campaign-id)
    (set-loading! true)
    (set-error! nil)
    (-> (js/Promise.all
         #js [(api/api-fetch (str "/campaigns/" campaign-id "/documents"))
              (api/api-fetch (str "/campaigns/" campaign-id "/summary"))])
        (.then (fn [results]
                 (set-documents! (aget results 0))
                 (set-summary! (aget results 1))
                 (set-loading! false)))
        (.catch (fn [err]
                  (set-error! (if (instance? js/Error err) (.-message err) "Erreur réseau"))
                  (set-loading! false))))))

(defui document-card [{:keys [doc]}]
  ($ Link {:class "card"
           :to (str "/documents/" (.-id doc))}
    ($ :h3 (.-filename doc))
    ($ :p.muted
      (str (.-page_count doc) " pages · "
           (.-section_count doc) " sections · "
           (.-chunk_count doc) " chunks"))
    (when-let [status (.-latest_ingestion_status doc)]
      ($ :p.muted (str "Import raw : " status)))))

(defui document-picker-page []
  (let [params (useParams)
        campaign-id (.-campaignId params)
        [documents set-documents!] (uix/use-state nil)
        [summary set-summary!] (uix/use-state nil)
        [error set-error!] (uix/use-state nil)
        [loading set-loading!] (uix/use-state true)
        load (uix/use-callback
              #(fetch-documents! campaign-id set-documents! set-summary! set-error! set-loading!)
              [campaign-id])]
    (uix/use-effect
      (fn []
        (load)
        js/undefined)
      [load])
    (cond
      loading ($ :main.page ($ loading-state))
      error ($ :main.page ($ error-state {:message error :on-retry load}))
      (or (nil? documents) (zero? (.-length documents)))
      ($ :main.page
        ($ empty-state
          {:title (str "Aucun document pour " campaign-id)
           :message "Importez un PDF avec la CLI pour cette campagne."}))
      :else
      ($ :main.page
        ($ :h2 (str "Documents — " campaign-id))
        (when summary
          ($ :p.muted
            (str (.-section_count summary) " sections · "
                 (.-chunk_count summary) " chunks · "
                 (.-entities summary) " entités")))
        ($ :div.card-grid
          (for [^js doc documents]
            ($ document-card {:key (.-id doc) :doc doc})))))))
