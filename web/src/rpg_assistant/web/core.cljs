(ns rpg-assistant.web.core
  (:require ["react-router-dom" :refer [BrowserRouter Routes Route]]
            [re-frame.core :as rf]
            [uix.core :refer [defui $]]
            [uix.dom]
            [rpg-assistant.web.components.app-shell :refer [app-shell]]
            [rpg-assistant.web.events]
            [rpg-assistant.web.pages.campaign-list :refer [campaign-list-page]]
            [rpg-assistant.web.pages.document-explorer :refer [document-explorer-page]]
            [rpg-assistant.web.pages.document-picker :refer [document-picker-page]]
            [rpg-assistant.web.pages.stat-block-detail :refer [stat-block-detail-page]]
            [rpg-assistant.web.pages.stat-blocks :refer [stat-blocks-page]]
            [rpg-assistant.web.subs]))

(defui app []
  ($ BrowserRouter
    ($ Routes
      ($ Route {:element ($ app-shell)}
        ($ Route {:index true :element ($ campaign-list-page)})
        ($ Route {:path "campaigns/:campaignId" :element ($ document-picker-page)})
        ($ Route {:path "documents/:documentId" :element ($ document-explorer-page)})
        ($ Route {:path "documents/:documentId/chunks/:chunkId"
                  :element ($ document-explorer-page)})
        ($ Route {:path "documents/:documentId/stat-blocks" :element ($ stat-blocks-page)})
        ($ Route {:path "documents/:documentId/stat-blocks/:blockName"
                  :element ($ stat-block-detail-page)})))))

(defonce root (uix.dom/create-root (.getElementById js/document "root")))

(defn start []
  (rf/dispatch-sync [:init])
  (uix.dom/render-root ($ app) root))
