(ns rpg-assistant-web.views.document-explorer
  (:require [rpg-assistant-web.router :as router]
            [rpg-assistant-web.state :as state]
            [rpg-assistant-web.views.chunk-list :as chunk-list]
            [rpg-assistant-web.views.chunk-reader :as chunk-reader]
            [rpg-assistant-web.views.common :as common]
            [rpg-assistant-web.views.pdf :as pdf]
            [rpg-assistant-web.views.section-tree :as section-tree]))

(defn- pdf-modal [document-id page highlight pdf-state]
  [:div.pdf-modal-layer
   [:div.pdf-modal-backdrop
    {:on {:click [[:close-pdf-panel]]}
     :aria-hidden true}]
   [:div.pdf-modal.pdf-mobile.active
    (pdf/pdf-source-panel document-id page highlight pdf-state {:on-close? true})]])

(defn- explorer-columns
  [state document-id location section-id chunk-id sections chunks chunk
   mobile-tab pdf-visible pdf-state page highlight]
  [:div {:class (str "explorer-layout" (when pdf-visible " with-pdf"))}
   [:aside.explorer-column.side
    {:class (when (= mobile-tab :sections) "active")}
    [:h2.panel-title "Sections"]
    (when sections
      (section-tree/section-tree-view sections section-id))]

   [:section.explorer-column
    {:class (when (= mobile-tab :content) "active")}
    [:h2.panel-title (if chunk "Chunk" "Chunks")]
    (if chunk
      (chunk-reader/chunk-reader-view chunk)
      (when chunks
        (chunk-list/chunk-list-view document-id chunks {:selected-chunk-id chunk-id})))]

   (when pdf-visible
     [:aside.explorer-column.pdf-desktop
      {:class (str (when (= mobile-tab :pdf) "pdf-mobile active"))}
      (pdf/pdf-source-panel document-id page highlight pdf-state)])])

(defn document-explorer-view [state location]
  (let [params (:location/params location {})
        document-id (:document-id params)
        chunk-id (:chunk-id params)
        section-id (router/query-param location "section")
        explorer (state/explorer-state state document-id)
        {:keys [sections chunks chunk loading? error]} explorer
        {:keys [open page highlight mobile-open?]} (:pdf-panel state)
        mobile-tab (:mobile-tab state)
        pdf-visible (and open (some? page))
        pdf-state (state/pdf-state state document-id)]
    (cond
      loading? (common/loading-view)
      (and error (empty? sections)) (common/error-view error)
      :else
      [:div.explorer-page
       [:div.mobile-tabs
        [:button {:class (when (= mobile-tab :sections) "active")
                  :on {:click [[:set-mobile-tab "sections"]]}}
         "Sections"]
        [:button {:class (when (= mobile-tab :content) "active")
                  :on {:click [[:set-mobile-tab "content"]]}}
         "Contenu"]
        [:button {:class (when (= mobile-tab :pdf) "active")
                  :disabled (not pdf-visible)
                  :on {:click [[:set-mobile-tab "pdf"]]}}
         "PDF"]]
       (explorer-columns state document-id location section-id chunk-id sections
                         chunks chunk mobile-tab pdf-visible pdf-state page highlight)
       (when (and mobile-open? pdf-visible)
         (pdf-modal document-id page highlight pdf-state))])))
