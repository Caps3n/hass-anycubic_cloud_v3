import { CSSResult, LitElement, PropertyValues, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { commonFilesStyle } from "./styles";
import { platform } from "../../const";
import { localize } from "../../../localize/localize";
import {
  getPrinterEntities,
  getPrinterEntityIdPart,
  getPrinterSupportsMQTT,
} from "../../helpers";
import {
  AnycubicFileLocal,
  DomClickEvent,
  EvtTargFileInfo,
  HassDevice,
  HassEntityInfo,
  HassEntityInfos,
  HassPanel,
  HassRoute,
  HomeAssistant,
  LitTemplateResult,
} from "../../types";

interface FilePreviewResult {
  image: string | null;
}

export class AnycubicViewFilesBase extends LitElement {
  @property()
  public hass!: HomeAssistant;

  @property()
  public language!: string;

  @property({ type: Boolean, reflect: true })
  public narrow!: boolean;

  @property()
  public route!: HassRoute;

  @property()
  public panel!: HassPanel;

  @property({ attribute: "selected-printer-id" })
  public selectedPrinterID: string | undefined;

  @property({ attribute: "selected-printer-device" })
  public selectedPrinterDevice: HassDevice | undefined;

  @state()
  protected printerEntities: HassEntityInfos;

  @state()
  private printerEntityIdPart: string | undefined;

  @state()
  protected _fileArray: AnycubicFileLocal[] | undefined;

  @state()
  protected _listRefreshEntity: HassEntityInfo | undefined;

  @state()
  private _isRefreshing: boolean = false;

  @state()
  protected _isDeleting: boolean;

  @state()
  private _noMqttMessage: string;

  @state()
  private _supportsMQTT: boolean = false;

  @state()
  protected _httpResponse: boolean = false;

  // Only local/USB file lists have no built-in preview image of their own;
  // subclasses for those override this to opportunistically show a preview
  // from a matching past cloud print of the same file.
  protected previewEnabled: boolean = false;

  @state()
  private _previewImages = new Map<string, string | null>();

  private _previewRequested = new Set<string>();

  protected willUpdate(changedProperties: PropertyValues<this>): void {
    super.willUpdate(changedProperties);

    if (changedProperties.has("language")) {
      this._noMqttMessage = localize(
        "common.messages.mqtt_unsupported",
        this.language,
      );
    }

    if (
      changedProperties.has("hass") ||
      changedProperties.has("selectedPrinterID")
    ) {
      this.printerEntities = getPrinterEntities(
        this.hass,
        this.selectedPrinterID,
      );
      this.printerEntityIdPart = getPrinterEntityIdPart(this.printerEntities);
      this._supportsMQTT = getPrinterSupportsMQTT(
        this.hass,
        this.printerEntities,
        this.printerEntityIdPart,
      );
    }

    if (changedProperties.has("selectedPrinterID")) {
      this._previewImages = new Map();
      this._previewRequested.clear();
    }
  }

  render(): LitTemplateResult {
    return html`
      <div class="files-card" elevation="2">
        <button
          .disabled=${(!this._httpResponse && !this._supportsMQTT) || this._isRefreshing}
          class="file-refresh-button"
          @click=${this.refreshList}
        >
          <ha-icon
            class="file-refresh-icon"
            icon="mdi:refresh"
          >
          </ha-icon>
        </button>
        ${
          !this._httpResponse && !this._supportsMQTT
            ? html` <div class="no-mqtt-msg">${this._noMqttMessage}</div> `
            : nothing
        }
        <ul class="files-container">
        ${
          this._fileArray
            ? this._fileArray.map(
                (fileInfo) => html`
                  <li class="file-info">
                    ${this._renderPreview(fileInfo)}
                    <div class="file-name">${fileInfo.name}</div>
                    <button
                      class="file-delete-button"
                      .disabled=${this._isDeleting}
                      .file_info=${fileInfo}
                      @click=${this.deleteFile}
                    >
                      <ha-icon
                        class="file-delete-icon"
                        icon="mdi:delete"
                      ></ha-icon>
                    </button>
                  </li>
                `,
              )
            : null
        }
      </div>
    `;
  }

  refreshList = (): void => {
    if (this._listRefreshEntity) {
      this._isRefreshing = true;
      this.hass
        .callService("button", "press", {
          entity_id: this._listRefreshEntity.entity_id,
        })
        .then(() => {
          this._isRefreshing = false;
        })
        .catch((_e: unknown) => {
          this._isRefreshing = false;
        });
    }
  };

  // eslint-disable-next-line no-empty-function
  deleteFile = (_ev: DomClickEvent<EvtTargFileInfo>): void => {};

  private _renderPreview(
    fileInfo: AnycubicFileLocal,
  ): LitTemplateResult | typeof nothing {
    if (!this.previewEnabled || !fileInfo.name) {
      return nothing;
    }

    if (!this._previewImages.has(fileInfo.name)) {
      this._fetchPreview(fileInfo.name);
      return nothing;
    }

    const image = this._previewImages.get(fileInfo.name);

    if (!image) {
      return nothing;
    }

    return html`<img class="file-preview-thumb" src=${image} alt="" />`;
  }

  private _fetchPreview(filename: string): void {
    if (this._previewRequested.has(filename) || !this.selectedPrinterDevice) {
      return;
    }

    this._previewRequested.add(filename);

    this.hass
      .callWS<FilePreviewResult>({
        type: `${platform}/file_preview`,
        config_entry: this.selectedPrinterDevice.primary_config_entry,
        device_id: this.selectedPrinterDevice.id,
        filename,
      })
      .then((result) => {
        this._previewImages = new Map(this._previewImages).set(
          filename,
          result.image,
        );
      })
      .catch((_e: unknown) => {
        this._previewImages = new Map(this._previewImages).set(filename, null);
      });
  }

  static get styles(): CSSResult {
    return css`
      ${commonFilesStyle}
    `;
  }
}
