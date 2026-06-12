(ns rpg-assistant.web.pages.campaign-list
  (:require ["react-router-dom" :refer [Link]]
            [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.api :as api]
            [rpg-assistant.web.components.common :refer [loading-state error-state empty-state]]))

(defn- campaign-subtitle [^js campaign]
  (str (.-document_count campaign) " document(s)"
       (when-let [gs (.-game_system campaign)]
         (str " · " gs))))

(defn- fetch-campaigns! [set-campaigns! set-error! set-loading!]
  (set-loading! true)
  (set-error! nil)
  (-> (api/api-fetch "/campaigns")
      (.then (fn [data]
               (set-campaigns! data)
               (set-loading! false)))
      (.catch (fn [err]
                (set-error! (if (instance? js/Error err) (.-message err) "Erreur réseau"))
                (set-loading! false)))))

(defui campaign-card [{:keys [campaign]}]
  ($ Link {:class "card"
           :to (str "/campaigns/" (.-id campaign))}
    ($ :h3 (or (.-title campaign) (.-id campaign)))
    ($ :p.muted (campaign-subtitle campaign))))

(defui campaign-list-page []
  (let [[campaigns set-campaigns!] (uix/use-state nil)
        [error set-error!] (uix/use-state nil)
        [loading set-loading!] (uix/use-state true)
        load (uix/use-callback
              #(fetch-campaigns! set-campaigns! set-error! set-loading!)
              [])]
    (uix/use-effect
      (fn []
        (load)
        js/undefined)
      [load])
    (cond
      loading ($ :main.page ($ loading-state))
      error ($ :main.page ($ error-state {:message error :on-retry load}))
      (or (nil? campaigns) (zero? (.-length campaigns)))
      ($ :main.page
        ($ empty-state
          {:title "Aucune campagne importée"
           :message "Importez un PDF via la CLI :"
           :children ($ :pre {:style #js {:textAlign "left" :overflow "auto"}}
                         "uv run rpg-ingest raw extract <fichier.pdf> \\\n  --campaign-id momie --game-system cof2")}))
      :else
      ($ :main.page
        ($ :h2 "Campagnes")
        ($ :div.card-grid
          (for [^js campaign campaigns]
            ($ campaign-card {:key (.-id campaign) :campaign campaign})))))))
