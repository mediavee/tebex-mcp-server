import type { Config } from "../config.js";

export interface PaymentEntry {
  txn_id: string;
  date: string;
  price: string;
  currency: string;
  status: string;
  player: { id: number; name: string; uuid: string };
  packages: Array<{ id: number; name: string }>;
  [key: string]: unknown;
}

export interface PagedPaymentsResponse {
  pagination: { current_page: number; last_page: number };
  data: PaymentEntry[];
}

export class TebexError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = "TebexError";
  }
}

/**
 * Thin wrapper around the Tebex Plugin API (https://plugin.tebex.io).
 *
 * Auth: X-Tebex-Secret header with the server secret key.
 * Rate limit: 500 requests per 5-minute window.
 */
export class TebexClient {
  private readonly base = "https://plugin.tebex.io";
  private readonly headers: Record<string, string>;

  constructor(config: Config) {
    this.headers = {
      Accept: "application/json",
      "X-Tebex-Secret": config.tebexSecret,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    options: {
      query?: Record<string, string | number | boolean | undefined>;
      body?: unknown;
    } = {},
  ): Promise<T> {
    const url = new URL(this.base + path);
    if (options.query) {
      for (const [k, v] of Object.entries(options.query)) {
        if (v !== undefined) url.searchParams.set(k, String(v));
      }
    }

    const init: RequestInit = {
      method,
      headers: { ...this.headers },
    };

    if (options.body !== undefined) {
      init.body = JSON.stringify(options.body);
      (init.headers as Record<string, string>)["Content-Type"] =
        "application/json";
    }

    const res = await fetch(url, init);

    if (res.status === 204) {
      return undefined as T;
    }

    const text = await res.text();
    let parsed: unknown = text;
    if (text.length > 0) {
      try {
        parsed = JSON.parse(text);
      } catch {
        // leave as raw text
      }
    }

    if (!res.ok) {
      throw new TebexError(
        `Tebex API ${method} ${path} failed: ${res.status} ${res.statusText}`,
        res.status,
        parsed,
      );
    }

    return parsed as T;
  }

  // ───────────────────────────────── Information ──────────────────────────────────

  getInformation() {
    return this.request<unknown>("GET", "/information");
  }

  // ───────────────────────────────── Command Queue ────────────────────────────────

  getCommandQueue() {
    return this.request<unknown>("GET", "/queue");
  }

  getOfflineCommands() {
    return this.request<unknown>("GET", "/queue/offline-commands");
  }

  getOnlineCommands(playerId: number) {
    return this.request<unknown>(
      "GET",
      `/queue/online-commands/${playerId}`,
    );
  }

  deleteCommands(ids: number[]) {
    return this.request<void>("DELETE", "/queue", { body: { ids } });
  }

  // ───────────────────────────────── Listing ──────────────────────────────────────

  getListing() {
    return this.request<unknown>("GET", "/listing");
  }

  // ───────────────────────────────── Packages ─────────────────────────────────────

  listPackages() {
    return this.request<unknown>("GET", "/packages");
  }

  getPackage(packageId: number) {
    return this.request<unknown>("GET", `/packages/${packageId}`);
  }

  updatePackage(
    packageId: number,
    data: { disabled?: boolean; name?: string; price?: number },
  ) {
    return this.request<void>("PUT", `/package/${packageId}`, { body: data });
  }

  // ───────────────────────────────── Community Goals ──────────────────────────────

  listCommunityGoals() {
    return this.request<unknown>("GET", "/community_goals");
  }

  getCommunityGoal(goalId: number) {
    return this.request<unknown>("GET", `/community_goals/${goalId}`);
  }

  // ───────────────────────────────── Payments ─────────────────────────────────────

  listPayments(limit?: number) {
    return this.request<unknown>("GET", "/payments", {
      query: limit ? { limit } : undefined,
    });
  }

  listPaymentsPaged(page?: number) {
    return this.request<PagedPaymentsResponse>("GET", "/payments", {
      query: { paged: 1, page: page ?? 1 },
    });
  }

  getPayment(transactionId: string) {
    return this.request<unknown>("GET", `/payments/${transactionId}`);
  }

  getPaymentFields(packageId: number) {
    return this.request<unknown>("GET", `/payments/fields/${packageId}`);
  }

  createPayment(data: {
    note: string;
    packages: Array<{ id: number; options: Record<string, string> }>;
    price: number;
    ign: string;
  }) {
    return this.request<void>("POST", "/payments", { body: data });
  }

  updatePayment(
    transactionId: string,
    data: { username?: string; status?: "complete" | "chargeback" | "refund" },
  ) {
    return this.request<void>("PUT", `/payments/${transactionId}`, {
      body: data,
    });
  }

  addPaymentNote(transactionId: string, note: string) {
    return this.request<unknown>("POST", `/payments/${transactionId}/note`, {
      body: { note },
    });
  }

  // ───────────────────────────────── Checkout ─────────────────────────────────────

  createCheckout(packageId: number, username: string) {
    return this.request<unknown>("POST", "/checkout", {
      body: { package_id: packageId, username },
    });
  }

  // ───────────────────────────────── Gift Cards ───────────────────────────────────

  listGiftCards() {
    return this.request<unknown>("GET", "/gift-cards");
  }

  getGiftCard(giftCardId: number) {
    return this.request<unknown>("GET", `/gift-cards/${giftCardId}`);
  }

  lookupGiftCard(code: string) {
    return this.request<unknown>("GET", `/gift-cards/lookup/${code}`);
  }

  createGiftCard(data: {
    expires_at: string;
    note: string;
    amount: number;
  }) {
    return this.request<unknown>("POST", "/gift-cards", { body: data });
  }

  topupGiftCard(giftCardId: number, amount: number) {
    return this.request<unknown>("PUT", `/gift-cards/${giftCardId}`, {
      body: { amount },
    });
  }

  voidGiftCard(giftCardId: number) {
    return this.request<void>("DELETE", `/gift-cards/${giftCardId}`);
  }

  // ───────────────────────────────── Coupons ──────────────────────────────────────

  listCoupons() {
    return this.request<unknown>("GET", "/coupons");
  }

  getCoupon(couponId: number) {
    return this.request<unknown>("GET", `/coupons/${couponId}`);
  }

  createCoupon(data: {
    code: string;
    effective_on: "package" | "category" | "cart";
    packages?: number[];
    categories?: number[];
    discount_type: "value" | "percentage";
    discount_amount?: number;
    discount_percentage?: number;
    redeem_unlimited: boolean;
    expire_never: boolean;
    expire_limit?: number;
    expire_date?: string;
    start_date?: string;
    basket_type: "single" | "subscription" | "both";
    minimum: number;
    discount_application_method: number;
    username?: string;
    note?: string;
  }) {
    return this.request<unknown>("POST", "/coupons", { body: data });
  }

  deleteCoupon(couponId: number) {
    return this.request<void>("DELETE", `/coupons/${couponId}`);
  }

  // ───────────────────────────────── Bans ─────────────────────────────────────────

  listBans() {
    return this.request<unknown>("GET", "/bans");
  }

  createBan(data: { reason: string; ip?: string; user?: string }) {
    return this.request<unknown>("POST", "/bans", { body: data });
  }

  // ───────────────────────────────── Sales ────────────────────────────────────────

  listSales() {
    return this.request<unknown>("GET", "/sales");
  }

  // ───────────────────────────────── Player Lookup ────────────────────────────────

  lookupPlayer(identifier: string) {
    return this.request<unknown>("GET", `/user/${identifier}`);
  }

  getPlayerPackages(playerId: number, packageId?: number) {
    return this.request<unknown>("GET", `/player/${playerId}/packages`, {
      query: packageId ? { package: packageId } : undefined,
    });
  }
}
