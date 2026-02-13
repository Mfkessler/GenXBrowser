export const ccByMappings: Record<string, string> = {
  SA: "ShareAlike",
  BY: "",
  NC: "NonCommercial",
  ND: "NoDerivatives",
  0: "",
};

export function getCcByMappings(keys: string): [string, string, string] {
  //returns [shortform, text, link]
  if (keys === "0") {
    return [
      "CC0 1.0",
      "CC0 1.0 Universal",
      "https://creativecommons.org/publicdomain/zero/1.0/",
    ];
  } else {
    const parts = ["BY", ...keys.split("-").filter(Boolean)];
    const shortform = `CC ${parts.join("-")} 4.0`;
    const text =
      "Attribution" +
      parts
        .slice(1) // skip BY, as it's Attribution
        .map((key) => (ccByMappings[key] ? "-" + ccByMappings[key] : ""))
        .join("") +
      " 4.0 International";
    const url =
      "https://creativecommons.org/licenses/" +
      parts.map((key) => key.toLowerCase()).join("-") +
      "/4.0/";

    return [shortform, text, url];
  }
}
