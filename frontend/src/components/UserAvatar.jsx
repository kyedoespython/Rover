import React from "react";

export default function UserAvatar({ href, label = "Open profile", large = false }) {
    const className = `user-avatar${large ? " user-avatar-large" : ""}`;
    const icon = (
        <svg aria-hidden="true" viewBox="0 0 24 24">
            <circle cx="12" cy="8" r="3.5" />
            <path d="M4.5 20c.7-3.8 3.2-5.8 7.5-5.8s6.8 2 7.5 5.8" />
        </svg>
    );

    return href ? (
        <a aria-label={label} className={className} href={href} title={label}>
            {icon}
        </a>
    ) : (
        <div aria-label="Default user avatar" className={className} role="img">
            {icon}
        </div>
    );
}
