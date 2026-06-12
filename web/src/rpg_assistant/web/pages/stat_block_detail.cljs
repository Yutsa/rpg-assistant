(ns rpg-assistant.web.pages.stat-block-detail
  (:require ["react-router-dom" :refer [Link useParams]]
            [re-frame.uix :refer [use-subscribe]]
            [uix.core :as uix :refer [defui $]]
            [rpg-assistant.web.api :as api]
            [rpg-assistant.web.components.common :refer [loading-state error-state]]
            [rpg-assistant.web.components.pdf-source-panel :refer [pdf-source-panel]]
            [rpg-assistant.web.components.stat-block-detail-view :refer [stat-block-detail-view]]))

(def ^:private detail-layout-style
  (js-obj "minHeight" (str 60 "vh")))

(def ^:private detail-column-style
  (js-obj "borderRight" (str "1px solid var(" "--border)")))

(defn- fetch-detail!
  [document-id decoded-name set-detail! set-candidates! set-error! set-loading!]
  (when (and (seq document-id) (seq decoded-name))
    (set-loading! true)
    (set-error! nil)
    (set-candidates! nil)
    (-> (api/api-fetch (str "/documents/" document-id "/stat-blocks/"
                             (js/encodeURIComponent decoded-name)))
        (.then (fn [data]
                 (set-detail! data)
                 (set-loading! false)))
        (.catch (fn [err]
                  (if (= (api/error-status err) 422)
                    (do
                      (set-candidates! (.-candidates (api/error-body err)))
                      (set-error! "Plusieurs fiches correspondent a ce nom."))
                    (set-error! (if (instance? js/Error err)
                                  (.-message err)
                                  "Fiche introuvable")))
                  (set-loading! false))))))

(defn- candidate-row [document-id ^js candidate]
  ($ :li {:key (.-chunk_id candidate)}
    ($ Link
      {:to (str "/documents/" document-id "/stat-blocks/"
                (js/encodeURIComponent (.-name candidate)))}
      (str (.-name candidate) " (NC " (or (.-nc candidate) "-")
           ", p." (.-start (.-pages candidate)) ")"))))

(defui stat-block-detail-page []
  (let [params (useParams)
        document-id (aget params "documentId")
        block-name (aget params "blockName")
        decoded-name (when block-name (js/decodeURIComponent block-name))
        pdf-panel (use-subscribe [:pdf-panel])
        pdf-visible (use-subscribe [:pdf-visible?])
        [detail set-detail!] (uix/use-state nil)
        [candidates set-candidates!] (uix/use-state nil)
        [error set-error!] (uix/use-state nil)
        [loading set-loading!] (uix/use-state true)]
    (uix/use-effect
      (fn []
        (fetch-detail! document-id decoded-name
                       set-detail! set-candidates! set-error! set-loading!)
        js/undefined)
      [document-id decoded-name])
    (cond
      loading
      ($ :main.page ($ loading-state))

      (and candidates (pos? (.-length candidates)))
      ($ :main.page
        ($ :div.state-box
          ($ :p error)
          ($ :ul
            (for [^js candidate candidates]
              (candidate-row document-id candidate)))))

      (or error (nil? detail))
      ($ :main.page ($ error-state {:message (or error "Fiche introuvable")}))

      :else
      ($ :div.explorer-layout {:style detail-layout-style}
        ($ :section.explorer-column {:style detail-column-style}
          ($ stat-block-detail-view {:detail detail}))
        (when pdf-visible
          ($ :aside.explorer-column
            ($ pdf-source-panel {:document-id document-id
                                 :page (:page pdf-panel)
                                 :highlight (:highlight pdf-panel)})))))))
