(ns rpg-assistant.web.pages.stat-blocks
  (:require ["react-router-dom" :refer [useParams]]
            [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.api :as api]
            [rpg-assistant.web.components.common :refer [loading-state error-state]]
            [rpg-assistant.web.components.stat-block-card :refer [stat-block-card]]))

(defn- sort-by-name [entries]
  (.slice (.sort entries
                  (fn [a b]
                    (.localeCompare (.-name a) (.-name b) "fr"))) 0))

(defn- fetch-entries! [document-id set-entries! set-error! set-loading!]
  (when (seq document-id)
    (set-loading! true)
    (-> (api/api-fetch (str "/documents/" document-id "/stat-blocks"))
        (.then (fn [data]
                 (set-entries! data)
                 (set-loading! false)))
        (.catch (fn [err]
                  (set-error! (if (instance? js/Error err) (.-message err) "Erreur"))
                  (set-loading! false))))))

(defui stat-blocks-page []
  (let [params (useParams)
        document-id (.-documentId params)
        [entries set-entries!] (uix/use-state #js [])
        [filter-text set-filter-text!] (uix/use-state "")
        [error set-error!] (uix/use-state nil)
        [loading set-loading!] (uix/use-state true)]
    (uix/use-effect
      (fn []
        (fetch-entries! document-id set-entries! set-error! set-loading!)
        js/undefined)
      [document-id])
    (let [query (.. filter-text trim toLowerCase)
          sorted (sort-by-name entries)
          filtered (if (seq query)
                     (.filter sorted (fn [^js entry]
                                       (.includes (.toLowerCase (.-name entry)) query)))
                     sorted)]
      (cond
        loading ($ :main.page ($ loading-state))
        error ($ :main.page ($ error-state {:message error}))
        :else
        ($ :main.page
          ($ :h2 "Fiches COF2")
          ($ :input {:type "search"
                     :placeholder "Filtrer par nom…"
                     :value filter-text
                     :on-change #(set-filter-text! (.. % -target -value))
                     :style #js {:width "100%"
                                :maxWidth "420px"
                                :padding "0.5rem"
                                :marginBottom "1rem"
                                :border "1px solid var(--border)"
                                :borderRadius "8px"}})
          (if (zero? (.-length filtered))
            ($ :p.muted "Aucune fiche stat pour ce document.")
            ($ :div.card-grid
              (for [^js entry filtered]
                ($ stat-block-card {:key (.-chunk_id entry)
                                    :document-id document-id
                                    :entry entry})))))))))
