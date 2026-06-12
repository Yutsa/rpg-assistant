(ns rpg-assistant.web.pages.document-explorer
  (:require ["react-router-dom" :refer [useParams useSearchParams useNavigate]]
            [re-frame.core :as rf]
            [re-frame.uix :refer [use-subscribe]]
            [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.api :as api]
            [rpg-assistant.web.components.chunk-list :refer [chunk-list]]
            [rpg-assistant.web.components.chunk-reader :refer [chunk-reader]]
            [rpg-assistant.web.components.common :refer [loading-state error-state]]
            [rpg-assistant.web.components.pdf-source-panel :refer [pdf-source-panel]]
            [rpg-assistant.web.components.section-tree :refer [section-tree]]))

(defn- pick-section-id [^js data section-id]
  (if (and section-id (some (fn [^js s] (= (.-id s) section-id)) data))
    section-id
    (when (pos? (.-length data))
      (.-id (aget data 0)))))

(defn- load-sections!
  [document-id section-id set-sections! set-search-params! set-error! set-loading!]
  (when (seq document-id)
    (set-loading! true)
    (set-error! nil)
    (-> (api/api-fetch (str "/documents/" document-id "/sections"))
        (.then (fn [data]
                 (set-sections! data)
                 (let [selected (pick-section-id data section-id)]
                   (when (and selected (not= selected section-id))
                     (set-search-params! #js {:section selected} #js {:replace true})))
                 (set-loading! false)))
        (.catch (fn [err]
                  (set-error! (if (instance? js/Error err) (.-message err) "Erreur"))
                  (set-loading! false))))))

(defn- load-chunks! [document-id section-id set-chunks! set-error!]
  (if (and (seq document-id) (seq section-id))
    (-> (api/api-fetch (str "/documents/" document-id "/chunks?section_id="
                            (js/encodeURIComponent section-id) "&limit=50"))
        (.then set-chunks!)
        (.catch (fn [err]
                  (set-error! (if (instance? js/Error err) (.-message err) "Erreur")))))
    (set-chunks! #js [])))

(defn- load-chunk! [chunk-id set-chunk! set-error!]
  (if (seq chunk-id)
    (-> (api/api-fetch (str "/chunks/" chunk-id))
        (.then set-chunk!)
        (.catch (fn [err]
                  (set-error! (if (instance? js/Error err) (.-message err) "Chunk introuvable")))))
    (set-chunk! nil)))

(defui explorer-content
  [{:keys [document-id section-id sections chunks chunk select-section
           mobile-tab set-mobile-tab! pdf-visible pdf-panel pdf-mobile-open]}]
  ($ :<>
    ($ :div.mobile-tabs
      ($ :button {:type "button"
                  :class (when (= mobile-tab "sections") "active")
                  :on-click #(set-mobile-tab! "sections")}
        "Sections")
      ($ :button {:type "button"
                  :class (when (= mobile-tab "content") "active")
                  :on-click #(set-mobile-tab! "content")}
        "Contenu")
      ($ :button {:type "button"
                  :class (when (= mobile-tab "pdf") "active")
                  :disabled (not pdf-visible)
                  :on-click #(set-mobile-tab! "pdf")}
        "PDF"))
    ($ :div.explorer-layout {:class (when pdf-visible "with-pdf")}
      ($ :aside.explorer-column.side
        {:class (when (= mobile-tab "sections") "active")}
        ($ :h2.panel-title "Sections")
        ($ section-tree {:sections sections
                         :selected-id section-id
                         :on-select select-section}))
      ($ :section.explorer-column
        {:class (when (= mobile-tab "content") "active")}
        ($ :h2.panel-title (if chunk "Chunk" "Chunks"))
        (if chunk
          ($ chunk-reader {:chunk chunk :document-id document-id})
          ($ chunk-list {:document-id document-id :chunks chunks})))
      ($ :aside.explorer-column.pdf-desktop
        {:class (when (= mobile-tab "pdf") "pdf-mobile active")
         :style (when-not pdf-visible #js {:display "none"})}
        (when pdf-visible
          ($ pdf-source-panel {:document-id document-id
                               :page (:page pdf-panel)
                               :highlight (:highlight pdf-panel)}))))
    (when (and pdf-mobile-open pdf-visible)
      ($ :<>
        ($ :div.pdf-modal-backdrop
          {:on-click #(rf/dispatch [:pdf/close])
           :aria-hidden true})
        ($ :div.pdf-modal.pdf-mobile.active
          ($ pdf-source-panel {:document-id document-id
                               :page (:page pdf-panel)
                               :highlight (:highlight pdf-panel)
                               :on-close #(rf/dispatch [:pdf/close])}))))))

(defui document-explorer-page []
  (let [params (useParams)
        document-id (.-documentId params)
        chunk-id (.-chunkId params)
        [search-params set-search-params] (useSearchParams)
        navigate (useNavigate)
        section-id (.get search-params "section")
        pdf-panel (use-subscribe [:pdf-panel])
        pdf-visible (use-subscribe [:pdf-visible?])
        pdf-mobile-open (use-subscribe [:pdf-mobile-open])
        [sections set-sections!] (uix/use-state #js [])
        [chunks set-chunks!] (uix/use-state #js [])
        [chunk set-chunk!] (uix/use-state nil)
        [error set-error!] (uix/use-state nil)
        [loading set-loading!] (uix/use-state true)
        [mobile-tab set-mobile-tab!] (uix/use-state "content")
        select-section (uix/use-callback
                        (fn [id]
                          (set-search-params #js {:section id})
                          (navigate (str "/documents/" document-id))
                          (set-mobile-tab! "content"))
                        [document-id navigate set-search-params])]
    (uix/use-effect
      (fn []
        (load-sections! document-id section-id set-sections! set-search-params set-error! set-loading!)
        js/undefined)
      [document-id])
    (uix/use-effect
      (fn []
        (load-chunks! document-id section-id set-chunks! set-error!)
        js/undefined)
      [document-id section-id])
    (uix/use-effect
      (fn []
        (load-chunk! chunk-id set-chunk! set-error!)
        js/undefined)
      [chunk-id])
    (cond
      loading ($ loading-state)
      (and error (zero? (.-length sections)))
      ($ error-state {:message error})
      :else
      ($ explorer-content {:document-id document-id
                           :section-id section-id
                           :sections sections
                           :chunks chunks
                           :chunk chunk
                           :select-section select-section
                           :mobile-tab mobile-tab
                           :set-mobile-tab! set-mobile-tab!
                           :pdf-visible pdf-visible
                           :pdf-panel pdf-panel
                           :pdf-mobile-open pdf-mobile-open}))))
